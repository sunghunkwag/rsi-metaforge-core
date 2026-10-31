"""Track 1: the lowest validation loss after one epoch on 8xH100, without backpropagation; no time limit.

The baseline is Dust (https://qlabs.sh/research/dust) with Adam. No autograd or backward pass is used.
One update (DUST.step):
  1. A clean forward caches every layer's input and output, every block's input, and the per-token losses.
  2. Direct draws jitter a layer's output at every token, y + sigma * a with a ~ N(0, I), rerun the
     forward from that layer's block on, and reward each token's jitter with the loss reduction at that
     token (the first block's sites with the decayed reduction at it and after it). The reward-weighted
     noise, averaged over draws, is the estimated error at the layer's output.
  3. The attention internals (queries, keys, values, value-embedding gates, value embeddings) are
     credited through the estimated error at the attention output instead,
     recomputing only their block's attention.
  4. The head is jittered on the cached logits, one 256-column slab at a time.
  5. The outer product of each layer's estimated output error with its cached input, summed over
     tokens, is the layer's weight gradient, as in backprop. The 2L residual mixing scalars use
     two-sided weight-space ES. Then one Adam step.

Launch: torchrun --standalone --nproc_per_node=8 train/val/dust.py
"""
import argparse
from contextlib import nullcontext
from dataclasses import asdict, dataclass
import json
import math
import os
from pathlib import Path
import sys
import time

import torch
from torch import nn
from torch.nn import functional as F

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from utils.eval import evaluate
from utils.model import GPT, GPTConfig, attention, apply_rotary_emb, has_ve, norm
from utils.prepare_data import TRAIN_ROWS, load_rows

BATCH = 8            # sequences of 2,048 predictions per update; one epoch is 1,831 updates
SEED = 0


@dataclass
class Recipe:
    """Draws per update for each part of the model, summed over GPUs. Lists have one entry per block."""
    writers: list[int]      # draws per block for the attention and MLP output projections (c_proj), jittered together
    hidden: list[int]       # draws per block for the MLP's first layer (mlp.c_fc)
    hubs: list[int]         # draws per block for the attention output, before attn.c_proj
    embedding: int          # draws for the token embedding
    head: int               # draws for the output head (lm_head)
    local: dict[str, int]   # draws per block for each attention internal: q, v, gate, k, ve
    nrep: int               # at most this many draws run together in one forward pass
    lr: float               # Adam rate of the matrices and the head; embeddings get 300x, mixing scalars 30x
    betas: tuple = (0.7, 0.95)
    warmdown: float = 0.0   # final fraction of the epoch over which the learning rate decays linearly to 0
                            # (the noisy estimate leaves a loss floor that decaying the rate lowers)
    gamma: float = 0.98     # attention-internal credit decay per token of lag
    first_gamma: float = 0.3  # reward-to-go decay for the first block's direct draws


def recipe(scale):
    """The tuned 16k cell of the Adam ladder at 10M tokens (scale 1), with every count scaled.

    Under Adam the per-block draws are even, the MLP hidden layer and the attention outputs get twice the
    writers' draws, and the value embeddings get the most of the attention internals. The token embedding
    gets a quarter of that cell's draws: each one reruns the whole network, and at 10M tokens the cut costs
    nothing while saving about 30% of the time.
    """
    count = lambda k: max(64, round(k * scale / 64) * 64)  # 8 GPUs x chunks of at least 8 draws
    return Recipe(
        writers=[count(256)] * 8, hidden=[count(512)] * 8, hubs=[count(512)] * 8,
        embedding=count(2048), head=max(2048, round(49152 * scale / 2048) * 2048),
        local=dict(q=count(384), v=count(384), gate=count(128), k=count(1664), ve=count(4608)),
        nrep=16, lr=0.0015, warmdown=0.3,
    )


RECIPE = recipe(1.5)


def chunk_size(draws, cap):
    """The largest count up to cap that divides draws: that many draws share one batched forward."""
    return next(n for n in range(min(cap, draws), 0, -1) if draws % n == 0)


def reward_to_go(reward, gamma):
    """Credit each token with the loss reductions at it and after it, decayed by gamma per token."""
    lags = math.ceil(math.log(1e-6) / math.log(gamma))
    kernel = gamma ** torch.arange(lags, device=reward.device, dtype=reward.dtype)
    padded = F.pad(reward.flatten(0, 1).unsqueeze(1), (0, lags - 1))
    return F.conv1d(padded, kernel.view(1, 1, -1)).view_as(reward)


@torch.compile
def head_loss(x, weight, targets, vocab):
    """GPT.forward's final norm, head, logit soft cap and per-token cross-entropy, fused by compile."""
    logits = F.linear(norm(x), weight)[..., :vocab].float()
    logits = 15 * torch.tanh(logits / 15)
    return F.cross_entropy(logits.flatten(0, 1), targets.flatten(), ignore_index=-1, reduction='none')


# The direct draws' jitter sites inside a block, by block_forward's argument name.
SITES = {'o': 'o@{}', 'attn': 'transformer.h.{}.attn.c_proj', 'fc': 'transformer.h.{}.mlp.c_fc',
         'mlp': 'transformer.h.{}.mlp.c_proj'}
torch._dynamo.config.cache_size_limit = 64  # block_forward compiles per window, value embedding and site


@torch.compile
def block_forward(x, w, ve, cos, sin, window, o=None, attn=None, fc=None, mlp=None):
    """Block.forward with a draw's jitter added at the attention output (o), the attention or MLP output
    projection (attn, mlp) or the MLP hidden layer (fc). Without hooks, compile fuses the elementwise work.
    """
    add = lambda t, jitter: t if jitter is None else t + jitter
    B, T, C = x.shape
    h = norm(x)
    dim = 2 * cos.shape[-1]  # head size; the rotary tables cover half of it
    q, k, v = (F.linear(h, w[name]).view(B, T, -1, dim) for name in ('q', 'k', 'v'))
    if ve is not None:
        gate = 2 * torch.sigmoid(F.linear(h[..., :w['gate'].shape[1]], w['gate']))
        v = v + gate.unsqueeze(-1) * ve.view_as(v)
    q, k = norm(apply_rotary_emb(q, cos, sin)), norm(apply_rotary_emb(k, cos, sin))
    y = add(attention(q, k, v, window).reshape(B, T, C), o)
    x = x + add(F.linear(y, w['proj']), attn)
    hidden = add(F.linear(norm(x), w['fc']), fc)
    return x + add(F.linear(F.relu(hidden).square(), w['out']), mlp)


def average_ranks(tensor):
    if torch.distributed.is_initialized():
        torch.distributed.all_reduce(tensor, op=torch.distributed.ReduceOp.SUM)
        tensor.div_(torch.distributed.get_world_size())
    return tensor


class DUST:
    """
    The algorithm.

    Forward hooks on every Linear and Embedding capture its input and output during the clean pass, and
    pre-hooks capture every block's input, so a draw that jitters block l reruns only blocks l onward, through
    block_forward. The virtual sites o@{layer} are the attention outputs before attn.c_proj. Each GPU draws
    different noise for the same batch.
    """

    def __init__(self, model, recipe, seed=0, rank=0, world=1):
        self.model, self.recipe, self.world = model, recipe, world
        self.device = next(model.parameters()).device
        self.dtype = torch.bfloat16 if self.device.type == 'cuda' else torch.float32
        self.generator = torch.Generator(self.device).manual_seed(seed + 3 + 7777 * rank)
        self.modules = {n: m for n, m in model.named_modules() if isinstance(m, (nn.Linear, nn.Embedding))}
        self.inputs, self.outputs, self.blocks = {}, {}, {}
        self.weights = [dict(q=b.attn.c_q.weight, k=b.attn.c_k.weight, v=b.attn.c_v.weight,
                             gate=b.attn.ve_gate.weight if b.attn.ve_gate is not None else None,
                             proj=b.attn.c_proj.weight, fc=b.mlp.c_fc.weight, out=b.mlp.c_proj.weight)
                        for b in model.transformer.h]
        self.capturing = False

        counts = recipe.writers + recipe.hidden + recipe.hubs + [recipe.embedding, recipe.head]
        counts += list(recipe.local.values())
        if any(k % world for k in counts) or 8 % world:
            raise ValueError('Every draw count must split evenly across the GPUs.')
        head, slabs = recipe.head // world, model.config.vocab_size // 256
        if head // chunk_size(head, recipe.nrep) % slabs:
            raise ValueError('Head draws must visit each 256-column slab equally on every GPU.')

        self.hooks = [m.register_forward_hook(self.output_hook(n)) for n, m in self.modules.items()]
        for layer, block in enumerate(model.transformer.h):
            self.hooks.append(block.register_forward_pre_hook(self.block_hook(layer)))

    def autocast(self):
        return torch.autocast('cuda', dtype=self.dtype) if self.device.type == 'cuda' else nullcontext()

    def output_hook(self, name):
        def hook(module, args, output):
            if self.capturing:
                self.inputs[name] = args[0].float() if args[0].is_floating_point() else args[0]
                self.outputs[name] = output

        return hook

    def block_hook(self, layer):
        def hook(module, args):
            if self.capturing:
                self.blocks[layer] = args[0]

        return hook

    def close(self):
        for hook in self.hooks:
            hook.remove()

    def noise(self, *shape, dtype=None):
        return torch.randn(*shape, device=self.device, dtype=dtype or self.dtype, generator=self.generator)

    def losses(self, x, y):
        with self.autocast():
            return self.model(x, y, loss_reduction='none').view_as(y).float()

    def capture(self, x, y):
        self.x, self.y = x, y
        self.batch, self.length = x.shape
        self.capturing = True
        try:
            self.clean_loss = self.losses(x, y)
        finally:
            self.capturing = False
        with self.autocast():  # the normalized embedding every block mixes in, as in GPT.forward
            self.x0 = norm(self.outputs['transformer.wte'])

    def rerun(self, n, entry, jitter):
        """Per-token losses of n draws with additive jitter at sites of block entry, rerunning blocks entry
        onward from its captured input (entry None: every block, from the jittered token embedding).

        The tiny bfloat16 offset of this path from the clean full forward is common to every draw.
        """
        model, length = self.model, self.length
        cos, sin = model.cos[:, :length], model.sin[:, :length]
        with self.autocast():
            if entry is None:
                embedding = self.outputs['transformer.wte'].repeat(n, 1, 1)
                x = x0 = norm(embedding + jitter['transformer.wte'])
            else:
                x, x0 = self.blocks[entry].repeat(n, 1, 1), self.x0.repeat(n, 1, 1)
            for i in range(entry or 0, model.config.n_layer):
                if entry is None or i > entry:
                    x = model.resid_lambdas[i] * x + model.x0_lambdas[i] * x0
                ve = self.outputs.get(f'value_embeds.{i}')
                sites = {key: jitter.get(site.format(i)) for key, site in SITES.items()} if i == entry else {}
                x = block_forward(x, self.weights[i], None if ve is None else ve.repeat(n, 1, 1), cos, sin,
                                  model.window_sizes[i][0], **sites)
            loss = head_loss(x, model.lm_head.weight, self.y.repeat(n, 1), model.config.vocab_size)
        return loss.view(n, self.batch, length)

    def direct_errors(self, sites, draws, sigma, entry=None, gamma=0.0):
        """One-sided loss drops, centered across each chunk of draws.

        Sites live in block `entry` (None: the token embedding), so a draw reruns only the blocks from there
        on. gamma > 0 rewards each jitter with the decayed reward-to-go instead of its own token's reduction.
        """
        n = chunk_size(draws, self.recipe.nrep)
        width = lambda s: self.model.config.n_embd if s.startswith('o@') else self.outputs[s].shape[-1]
        errors = {s: torch.zeros(self.batch, self.length, width(s), device=self.device) for s in sites}

        for _ in range(draws // n):
            noise = {s: self.noise(n * self.batch, self.length, width(s)) for s in sites}
            perturbed_loss = self.rerun(n, entry, {s: sigma * a for s, a in noise.items()})

            reward = self.clean_loss.unsqueeze(0) - perturbed_loss
            if n > 1:
                reward = reward - reward.mean(0, keepdim=True)
            if gamma:
                reward = reward_to_go(reward, gamma)
            for site, a in noise.items():
                errors[site] -= torch.einsum(
                    'nbt,nbtd->btd', reward.to(self.dtype),
                    a.view(n, self.batch, self.length, -1),
                ).float() / sigma

        return {s: error / draws for s, error in errors.items()}

    def head_error(self, draws, sigma=0.1):
        """Perturb one vocabulary slab at a time; recompute CE from its changed logits.

        Each chunk jitters one 256-column slab of the cached logits, and the loss is recomputed from the
        cached sums of the other slabs. This is much cheaper than a forward pass, and each reward only
        reflects 256 jittered columns instead of all 4096.
        """
        n, b, t = chunk_size(draws, self.recipe.nrep), self.batch, self.length
        raw = self.outputs['lm_head']
        vocab, slab = self.model.config.vocab_size, 256
        slabs = vocab // slab
        logits = 15 * torch.tanh(raw[..., :vocab].float() / 15)
        slab_sums = logits.exp().view(b, t, slabs, slab).sum(-1)
        total = slab_sums.sum(-1)
        target = self.y.clamp(min=0)
        clean_target = logits.gather(-1, target.unsqueeze(-1)).squeeze(-1)
        target = target.repeat(n, 1)
        error = torch.zeros_like(raw, dtype=torch.float32)

        for chunk in range(draws // n):
            block = chunk % slabs
            lo = block * slab
            a = self.noise(n * b, t, slab)
            changed = raw[..., lo:lo + slab].float().repeat(n, 1, 1) + sigma * a.float()
            changed = 15 * torch.tanh(changed / 15)
            partition = (total - slab_sums[..., block]).repeat(n, 1) + changed.exp().sum(-1)
            in_slab = (target >= lo) & (target < lo + slab)
            target_logit = torch.where(
                in_slab,
                changed.gather(
                    -1, (target - lo).clamp(0, slab - 1).unsqueeze(-1),
                ).squeeze(-1),
                clean_target.repeat(n, 1),
            )
            loss = (partition.log() - target_logit).view(n, b, t)
            reward = torch.where(self.y.unsqueeze(0) != -1, self.clean_loss.unsqueeze(0) - loss, 0)
            if b > 1:
                reward = reward - reward.mean(1, keepdim=True)
            error[..., lo:lo + slab] -= torch.einsum(
                'nbt,nbtd->btd', (reward / sigma).to(self.dtype), a.view(n, b, t, slab),
            ).float()

        return error / (draws // slabs)

    def local_errors(self, kind, draws, targets, sigma=0.1):
        """Score attention-output changes against estimated output errors (no derivatives).

        Each draw recomputes the block's attention output from the cached clean activations and scores the
        change per head against the output's estimated error (`targets`, computed by direct_errors on the
        o@{layer} sites). Queries keep their own token's score; the other kinds sum the scores of later
        tokens, decayed by gamma per token.
        """
        cfg = self.model.config
        n = chunk_size(draws, self.recipe.nrep)
        b, t, h, d = self.batch, self.length, cfg.n_head, cfg.n_embd // cfg.n_head
        site_suffix = {'q': 'attn.c_q', 'k': 'attn.c_k', 'v': 'attn.c_v', 'gate': 'attn.ve_gate'}
        layers = [i for i in range(cfg.n_layer) if kind not in ('ve', 'gate') or has_ve(i, cfg.n_layer)]
        sites = {
            i: f'value_embeds.{i}' if kind == 've' else f'transformer.h.{i}.{site_suffix[kind]}'
            for i in layers
        }
        width = h if kind == 'gate' else cfg.n_embd
        errors = {i: torch.zeros(b, t, width, device=self.device) for i in layers}
        cos, sin = self.model.cos[:, :t].float(), self.model.sin[:, :t].float()

        def processed(raw):
            return norm(apply_rotary_emb(raw, cos, sin)).to(self.dtype)

        def repeat(x):
            return x.unsqueeze(0).expand(n, -1, -1, -1, -1).reshape(n * b, t, h, d)

        clean = {}
        for i in layers:
            prefix = f'transformer.h.{i}.attn.'
            q, k, v = [self.outputs[prefix + 'c_' + name].float().view(b, t, h, d) for name in ('q', 'k', 'v')]
            z = self.outputs[prefix + 've_gate'].float() if has_ve(i, cfg.n_layer) else None
            ve = self.outputs[f'value_embeds.{i}'].float().view(b, t, h, d) if z is not None else None
            values = v if z is None else v + (2 * torch.sigmoid(z)).unsqueeze(-1) * ve
            qp, kp = processed(q), processed(k)
            window = self.model.window_sizes[i][0]
            baseline = attention(qp, kp, values.to(self.dtype), window)
            positions = torch.arange(t, device=self.device)
            lag = positions[None, :] - positions[:, None]  # [perturbation position, output position]
            # credit[t, s]: how much of output s's score goes to the jitter at t, inside the causal window
            credit = ((lag >= 0) & (lag <= window)).float() * self.recipe.gamma ** lag.clamp(min=0)
            clean[i] = q, k, z, ve, qp, kp, values, baseline, credit

        for _ in range(draws // n):
            for i in layers:
                a = self.noise(n, b, t, width, dtype=torch.float32)
                q, k, z, ve, qp, kp, values, baseline, credit = clean[i]
                window = self.model.window_sizes[i][0]
                divisor = sigma
                if kind in ('q', 'k'):
                    raw = q if kind == 'q' else k
                    perturbed = processed(
                        (raw.unsqueeze(0) + sigma * a.view(n, b, t, h, d)).reshape(n * b, t, h, d)
                    )
                    qa, ka = (perturbed, repeat(kp)) if kind == 'q' else (repeat(qp), perturbed)
                    delta = (
                        attention(qa, ka, repeat(values.to(self.dtype)), window).view(n, b, t, h, d)
                        - baseline
                    )
                else:
                    if kind == 'gate':
                        delta_gate = 2 * torch.sigmoid(z + sigma * a) - 2 * torch.sigmoid(z - sigma * a)
                        delta_value = delta_gate.unsqueeze(-1) * ve
                        divisor = 2 * sigma
                    else:
                        delta_value = sigma * a.view(n, b, t, h, d)
                        if kind == 've':
                            delta_value = delta_value * (2 * torch.sigmoid(z)).unsqueeze(-1)
                    delta = attention(
                        repeat(qp), repeat(kp),
                        delta_value.reshape(n * b, t, h, d).to(self.dtype), window,
                    ).view(n, b, t, h, d)

                score = torch.einsum('bthd,nbthd->nbth', targets[i].view(b, t, h, d).to(self.dtype), delta)
                if kind != 'q':
                    score = torch.einsum('nbsh,ts->nbth', score.float(), credit)
                estimate = torch.einsum('nbth,nbthd->bthd', score.float(), a.view(n, b, t, h, -1))
                errors[i] += estimate.reshape(b, t, width) / divisor

        return {sites[i]: errors[i] / draws for i in layers}

    def reassemble(self, site, error):
        """The exact local linear map: error times input, or scatter-add for an embedding. """
        x, module = self.inputs[site], self.modules[site]
        if isinstance(module, nn.Embedding):
            weight_error = torch.zeros_like(module.weight, dtype=torch.float32)
            return weight_error.index_add_(0, x.reshape(-1), error.reshape(-1, error.shape[-1]))
        return torch.einsum('btd,bti->di', error, x)

    def scalar_gradients(self, draws, sigma=0.03):
        """Two-sided weight-space ES for the 2L residual mixing scalars, rewarded by the summed token loss."""
        parameters = [self.model.resid_lambdas, self.model.x0_lambdas]
        original = [p.clone() for p in parameters]
        estimate = torch.zeros(2, self.model.config.n_layer, device=self.device)
        try:
            for _ in range(draws):
                a = self.noise(2, self.model.config.n_layer, dtype=torch.float32)
                losses = []
                for sign in (1, -1):
                    for p, clean, direction in zip(parameters, original, a):
                        p.copy_(clean + sign * sigma * direction)
                    losses.append(self.losses(self.x, self.y))
                difference = (losses[0] - losses[1])[self.y != -1].sum() / (2 * sigma)
                estimate += difference * a / draws
        finally:
            for p, clean in zip(parameters, original):
                p.copy_(clean)
        return dict(zip(('resid_lambdas', 'x0_lambdas'), estimate))

    @torch.no_grad()
    def step(self, x, y, optimizer):
        """One clean pass, direct-loss estimates, local attention estimates, then an Adam update."""
        self.capture(x, y)
        r, world, layers = self.recipe, self.world, self.model.config.n_layer
        gradients = {}
        # Noise scales are twice the SGD recipe's under Adam, and the first block reads its credit from the
        # decayed reward-to-go: its jitter mostly pays off at later tokens.
        for layer in range(layers):
            prefix = f'transformer.h.{layer}.'
            gamma = r.first_gamma if layer == 0 else 0.0
            groups = [
                ([prefix + 'attn.c_proj', prefix + 'mlp.c_proj'], r.writers[layer]),
                ([prefix + 'mlp.c_fc'], r.hidden[layer]),
            ]
            for sites, count in groups:
                for site, error in self.direct_errors(sites, count // world, 0.4, layer, gamma).items():
                    gradients[site + '.weight'] = self.reassemble(site, error)

        site = 'transformer.wte'
        error = self.direct_errors([site], r.embedding // world, 0.8)[site]
        gradients[site + '.weight'] = self.reassemble(site, error)

        # Attention outputs, each block alone. The deeper half moves the loss too little at 0.4 for a readable
        # reward, so it uses 0.8. The targets are averaged over GPUs so that every GPU scores the attention
        # internals against the estimate from the whole population.
        targets = {}
        for layer in range(layers):
            site = f'o@{layer}'
            sigma = 0.4 if layer < layers // 2 else 0.8
            gamma = r.first_gamma if layer == 0 else 0.0
            error = self.direct_errors([site], r.hubs[layer] // world, sigma, layer, gamma)[site]
            targets[layer] = average_ranks(error)

        gradients['lm_head.weight'] = self.reassemble('lm_head', self.head_error(r.head // world))
        for kind, count in r.local.items():
            for site, error in self.local_errors(kind, count // world, targets).items():
                gradients[site + '.weight'] = self.reassemble(site, error)
        gradients.update(self.scalar_gradients(8 // world))

        # Dividing the summed estimates by the token count gives the gradient of the mean loss.
        valid_tokens = (y != -1).sum()
        optimizer.zero_grad(set_to_none=True)
        for name, parameter in self.model.named_parameters():
            gradient = average_ranks((gradients[name] / valid_tokens).to(parameter.dtype))
            if not torch.isfinite(gradient).all():
                raise FloatingPointError(f'Non-finite estimate for {name}')
            parameter.grad = gradient
        optimizer.step()
        return self.clean_loss[y != -1].mean().item()


def make_model(device, seed):
    torch.manual_seed(seed)
    with torch.device('meta'):
        model = GPT(GPTConfig())
    model.to_empty(device=device)
    model.init_weights()
    # init output projections at std 1.5 / sqrt(fan_in)
    # instead of the zeros init_weights sets.
    with torch.no_grad():
        for name, module in model.named_modules():
            if 'c_proj' in name and isinstance(module, nn.Linear):
                scale = 1.5 * math.sqrt(3 / module.weight.shape[1])
                nn.init.uniform_(module.weight, -scale, scale)
    return model.requires_grad_(False)


def make_optimizer(model, recipe):
    """Adam at three rates: matrices and the head, embeddings (300x), residual mixing scalars (30x)."""
    groups = {}
    for name, parameter in model.named_parameters():
        scale = 300 if ('wte' in name or 'value_embeds' in name) else 30 if 'lambdas' in name else 1
        groups.setdefault(scale, []).append(parameter)
    return torch.optim.AdamW(
        [{'params': ps, 'lr': recipe.lr * scale} for scale, ps in groups.items()],
        betas=recipe.betas, eps=1e-8, weight_decay=0.0,
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--data-dir', type=Path, default=Path('data'))
    parser.add_argument('--output', type=Path, default=Path('logs/dust'))
    parser.add_argument('--scale', type=float, help='Scale every draw count of the 16k Adam cell instead.')
    parser.add_argument('--warmdown', type=float, help='Override the recipe\'s warmdown fraction.')
    parser.add_argument('--lr', type=float, help='Override the recipe\'s Adam learning rate.')
    parser.add_argument('--steps', type=int, help='Stop after this many updates (smoke tests).')
    parser.add_argument('--eval-every', type=int, default=0, help='Untimed validation every this many updates.')
    args = parser.parse_args()

    if not torch.cuda.is_available():
        parser.error('Training requires a CUDA GPU.')
    rank, world = int(os.environ.get('RANK', 0)), int(os.environ.get('WORLD_SIZE', 1))
    device = torch.device('cuda', int(os.environ.get('LOCAL_RANK', 0)))
    torch.cuda.set_device(device)
    torch.set_float32_matmul_precision('high')
    if world > 1:
        torch.distributed.init_process_group('nccl', device_id=device)
    settings = recipe(args.scale) if args.scale else RECIPE
    if args.warmdown is not None:
        settings.warmdown = args.warmdown
    if args.lr is not None:
        settings.lr = args.lr

    # One epoch: every training sequence feeds exactly one update.
    training = load_rows(args.data_dir / 'train.pt', TRAIN_ROWS)
    training = training[torch.randperm(len(training), generator=torch.Generator().manual_seed(SEED + 1))]
    steps = min(len(training) // BATCH, args.steps or len(training))
    if rank == 0:
        if args.output.exists() and any(args.output.iterdir()):
            raise FileExistsError(f'Choose an empty output directory: {args.output}')
        args.output.mkdir(parents=True, exist_ok=True)
        (args.output / 'config.json').write_text(json.dumps(dict(
            script=__file__, world=world, batch=BATCH, steps=steps, seed=SEED,
            recipe=asdict(settings), torch_version=torch.__version__,
        ), indent=2) + '\n')

    def init():
        model = make_model(device, SEED)
        return model, make_optimizer(model, settings), DUST(model, settings, SEED, rank, world)

    def set_rate(optimizer, step):
        left = (steps - step + 1) / steps  # fraction of the epoch still ahead, this update included
        for group in optimizer.param_groups:
            group.setdefault('initial_lr', group['lr'])
            group['lr'] = group['initial_lr'] * min(1.0, left / settings.warmdown if settings.warmdown else 1.0)

    # Untimed warmup on random tokens loads kernels and sets up communication. Everything is then rebuilt
    # from the seed, so the timed run starts exactly as if the warmup never happened.
    model, optimizer, estimator = init()
    noise = torch.randint(0, 4096, (BATCH, 2049), generator=torch.Generator().manual_seed(SEED)).to(device)
    estimator.step(noise[:, :-1].contiguous(), noise[:, 1:].contiguous(), optimizer)
    estimator.close()
    model, optimizer, estimator = init()

    if rank == 0:
        print(f'val: {steps} steps, recipe={asdict(settings)}, GPUs={world}', flush=True)
    log = (args.output / 'metrics.jsonl').open('a') if rank == 0 else None
    torch.cuda.synchronize()
    start, paused, elapsed = time.perf_counter(), 0.0, 0.0
    for step in range(1, steps + 1):
        batch = training[(step - 1) * BATCH:step * BATCH].to(device)
        set_rate(optimizer, step)
        loss = estimator.step(batch[:, :-1].contiguous(), batch[:, 1:].contiguous(), optimizer)
        torch.cuda.synchronize()
        elapsed = time.perf_counter() - start - paused
        record = dict(step=step, train_loss=loss, train_seconds=round(elapsed, 2))
        if args.eval_every and step % args.eval_every == 0 and step < steps:
            pause = time.perf_counter()
            record['val_loss'] = evaluate(model.state_dict(), args.data_dir)
            paused += time.perf_counter() - pause
        if rank == 0:
            print(json.dumps(record), flush=True)
            log.write(json.dumps(record) + '\n')

    estimator.close()
    state = {k: v.detach().cpu() for k, v in model.state_dict().items()}
    val_loss = evaluate(state, args.data_dir)
    if rank == 0:
        torch.save(state, args.output / 'final.pt')
        result = dict(val_loss=val_loss, train_seconds=round(elapsed, 2), steps=step,
                      tokens=step * BATCH * 2048)
        (args.output / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
        print(json.dumps(result), flush=True)
    if world > 1:
        torch.distributed.destroy_process_group()


if __name__ == '__main__':
    main()
