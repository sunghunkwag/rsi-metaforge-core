export const meta = {
  name: 'design-rsi6-acquisition',
  description: 'Judge panel: four independent designs of the smallest credible system that tests recursive improvement of capability acquisition on external tasks, three judges, one synthesis',
  phases: [
    { title: 'Design', detail: 'four designers, one angle each', model: 'opus' },
    { title: 'Judge', detail: 'three judges with different lenses score every design', model: 'opus' },
    { title: 'Synthesize', detail: 'one blueprint with work packages and a pre-registration skeleton; a critic attacks it', model: 'opus' },
  ],
}

const COPY = args.copy
const WORK = args.work

const RULES = [
  "You are a research engineer designing an experiment that will actually be built and run in the next hours. Vague designs are useless: every mechanism must be specified to the level of data structures, algorithms and the order of steps, and every claim about feasibility must be backed by a small measurement you ran or by arithmetic.",
  "",
  "HARD RULES.",
  "1. Read and run only inside " + COPY + " (a copy of parts of a repository) and " + WORK + " (shared material) and your own work directory (given below; create it). Never read, list, search or run anything under /home/user or /root/.claude or anywhere else. No filesystem-wide searches.",
  "2. Never look anywhere for directories named judge or files named seed.json, list_tasks2.json or test.json.",
  "3. Do not modify anything under " + COPY + " or the shared files in " + WORK + ". Your scripts and notes go into your own work directory. Set PYTHONDONTWRITEBYTECODE=1.",
  "4. No git, no network, no package installation.",
  "5. You may run small Python experiments (one process, every command under three minutes) to test an idea on the DEVELOPMENT puzzles in " + WORK + "/p3_development.json. Running a puzzle's sat function means executing external code with exec: do it only for those puzzles, with a time limit per call (signal.alarm) and bounded candidate sizes.",
  "6. The validation and test modules of the puzzle suite are sealed: you have their names and counts only. Do not try to recall or reconstruct their puzzles from memory; if you know this benchmark, design from the development modules and the summary alone, and say so if a design choice of yours rests on knowledge of the sealed part.",
].join("\n")

const CONTEXT = [
  "THE DIRECTIVE. Read " + COPY + "/rsi6/OWNER_DIRECTIVE.md completely and first. It is the specification. In short: build and test a system whose object of improvement is its own capability-acquisition mechanism M; at generation N the system, with M_N, meets unfamiliar problems, obtains verified feedback and proposes modifications to M_N; only independently validated modifications are adopted as M_(N+1); the question is whether M_(N+1) acquires genuinely new capabilities better than M_N at matched computational cost on unseen tasks and domains. Five arms are required at least (recursively modified; original frozen; skills retained but mechanism fixed; learned state reset between generations; nonrecursive with equal total compute). Accumulated solutions, caches and macros are not meta-level improvement. Not a toy: externally sourced, frozen, heterogeneous tasks; pre-registered thresholds; a claimed improvement must be able to fail.",
  "THE REPOSITORY. " + COPY + " holds the original runtime rsi_levels_metaforge_unified.py (49,316 lines; lines 17,171 to 38,369 are inert archived strings), README.md, EVIDENCE.md, OUTER_LOOP_CONSTITUTION.md and docs/. Read docs/P_RESULT.md and docs/ASCENT_P_SPEC.md (the Phase P saturation result the directive names: the self-driven loop re-saturated; its setter could not pose tasks that need capabilities outside its closure, and no extension was admitted), docs/05_limitations.md, and skim docs/K_RESULT.md, L_RESULT.md, M_RESULT.md, O_RESULT.md for the mechanisms that exist (witness-sealed tasks, an MDL gate for vocabulary growth, a ledger-trained proposal-ordering model with rollback, a proof kernel, counterfactual A/B gates, hash-chained ledgers with replay). The directive asks to preserve the repository's verification, evidence, reproducibility and rollback mechanisms and allows editing the runtime where needed. " + COPY + "/exploratory/shift_loop_20261110/README.md reports a recent study on list-processing tasks (vocabulary learning; its criteria were not established; its gain sat where a task contained a memorised routine): the directive explicitly moves beyond that kind of experiment.",
  "THE EXTERNAL TASKS CHOSEN SO FAR. " + WORK + "/p3_split_summary.txt: Python Programming Puzzles (397 verifier-defined puzzles in 18 modules, written by others). " + WORK + "/p3_development.json holds the development modules only (fields name, module, sat (source), ans_type, sol_header; instances of one puzzle differ in the default parameters of sat). A design may add other external sources (see the environment file) if it says exactly how they are obtained, frozen and split.",
  "THE ENVIRONMENT. " + WORK + "/environment.txt. Note especially: no language model can be called by the running system; language-model agents are developers and reviewers only.",
  "WHAT A DESIGN MUST CONTAIN. (1) What exactly M is: its parts, and which parts are 'mechanism' (algorithms, strategies, their parameters and structure) and which are 'learned state' (skills, weights, memories), because the five arms need that line. (2) How M_N proposes modifications to itself from its own experience, in a representation rich enough that the system is not merely tuning a few numbers, and how a proposal is validated independently before adoption. (3) How a capability is defined and verified on external tasks, what is hidden from the system, and what 'previously unavailable' means operationally. (4) The generational protocol and each of the five arms, with matched compute stated in countable units. (5) The measures the directive lists (acquisition success on unseen domains, cost per acquired capability, adaptation efficiency, cross-domain transfer, retention and regressions, attribution to the mechanism change, persistence over generations) with the statistical test for each and the failure thresholds. (6) The answer to the Phase P problem: how the system discovers, represents and pursues capabilities its current machinery cannot express, without capabilities being supplied by hand. (7) An implementation plan: files, core data structures, the order of work, estimated lines and hours, what is reused from the repository, and the compute cost of one development experiment and of the registered run. (8) Honest expectations: what will probably be measured, where the design will probably fail, and the exact assumption that limits its generality.",
].join("\n")

const DESIGN = {
  type: 'object',
  properties: {
    name: { type: 'string' },
    thesis: { type: 'string' },
    mechanism_and_state: { type: 'string' },
    self_modification: { type: 'string' },
    capability_definition: { type: 'string' },
    external_tasks: { type: 'string' },
    generations_and_arms: { type: 'string' },
    measures_and_tests: { type: 'string' },
    phase_p_answer: { type: 'string' },
    implementation_plan: { type: 'string' },
    compute_estimate: { type: 'string' },
    evidence_from_small_experiments: { type: 'string' },
    expected_results: { type: 'string' },
    risks_and_limits: { type: 'string' },
  },
  required: ['name', 'thesis', 'mechanism_and_state', 'self_modification', 'capability_definition', 'external_tasks', 'generations_and_arms', 'measures_and_tests', 'phase_p_answer', 'implementation_plan', 'compute_estimate', 'evidence_from_small_experiments', 'expected_results', 'risks_and_limits'],
}

const ANGLES = [
  {
    key: 'verifier-inversion',
    prompt: "YOUR ANGLE: acquisition as learning to invert verifiers, with the mechanism improving itself by solving puzzles about itself. Starting sketch (improve it or replace parts; you are not bound by it): a task is a verifier; the mechanism analyses the verifier's source (its syntax tree: constants, closed sub-expressions, conjuncts), derives a graded objective from it automatically (how far a candidate is from satisfying each conjunct), and searches the space of answers with typed mutation operators seeded from what it mined; solved instances of one puzzle are generalised into a program over the puzzle's parameters and checked on hidden instances; solved puzzles are generalised into schemas (a verifier pattern with holes and a construction of the answer) that later puzzles reuse. The meta level: the parameters and strategy programs of this mechanism are themselves an answer to a verifier-defined puzzle ('find a mechanism description that acquires more on recorded episodes than the incumbent'), which the mechanism solves with its own search; a solution is adopted only after validation on held-out domains. Make this concrete, test its core on the development puzzles (how many does a first version solve, at what cost), and say what the representation of M must be so that self-modification is more than tuning numbers.",
  },
  {
    key: 'open-world-tools',
    prompt: "YOUR ANGLE: acquisition as discovery from an open world. The system is not given an operator catalogue. It acquires executable operations and representations from what it meets: the source of the verifiers themselves (syntax fragments, library calls, idioms), the Python environment it runs in (modules and callables found by introspection and characterised by experiment), and its own verified solutions (abstractions). A capability is something the system could not compute before and can afterwards. The mechanism M is how it explores (what to probe, with which inputs, how much budget), how it characterises and indexes what it finds (behavioural signatures, types learned by execution), how it retrieves and composes operations for a task, and how it abstracts. Self-modification acts on those procedures. Design it so that it is safe (arbitrary library calls can delete files or hang: say exactly how the exploration is confined) and so that the Phase P problem gets a real answer. Test the core idea on the development puzzles.",
  },
  {
    key: 'learned-learner',
    prompt: "YOUR ANGLE: the acquisition mechanism as a learner whose own learning rule is learned. The Owner has also asked, in the same session, for a learned component whose weights are updated continually: learning while adapting, continual learning, transfer, meta-reinforcement learning. Design M around learned parts (non-transformer networks or other learned models in NumPy: proposal policies, value estimates, an update rule or fast-adaptation mechanism that is itself meta-learned), with a clear account of what is trained on what, online, with which reward, and of how catastrophic forgetting and regressions are detected and rolled back. The meta level must be more than a hyper-parameter sweep: the thing that changes between generations is how the system learns (for example a meta-learned update rule, exploration policy or credit-assignment scheme), proposed by the system from its own experience and validated on held-out domains. Be hard on yourself about sample efficiency: there are 97 development puzzles and 4 CPU cores. Test a small piece on the development puzzles.",
  },
  {
    key: 'open-ended-evolution',
    prompt: "YOUR ANGLE: open-ended, quality-diversity evolution of acquisition mechanisms. A population (archive) of mechanisms, each a program in a meta-language or a structured genome that describes how to search, what to remember and how to generalise; variation operators that are themselves part of the genome (so the way the system proposes modifications can improve); selection by acquisition performance on held-out domains with novelty or behavioural diversity kept; stepping stones retained. The recursive question becomes: do later mechanisms, bred by earlier ones, acquire new capabilities on unseen domains better at matched cost, and do mechanisms bred by improved mechanisms improve faster. Specify the meta-language concretely (its primitives must be generic search and learning operations, not solvers for particular domains), the evaluation cost of one mechanism and therefore how many can be evaluated, and the arms. Test a small piece on the development puzzles.",
  },
]

function designPrompt(a) {
  return [RULES, "", "Your work directory: " + WORK + "/design-" + a.key, "", CONTEXT, "", a.prompt, "",
    "Return your design in the structure asked for. In evidence_from_small_experiments report what you actually ran and what it printed (numbers), not what you expect."].join("\n")
}

phase('Design')
const designs = (await parallel(ANGLES.map(a => () =>
  agent(designPrompt(a), { label: 'design:' + a.key, phase: 'Design', schema: DESIGN, model: 'opus' }).then(d => d ? { key: a.key, ...d } : null)
))).filter(Boolean)
log('designs returned: ' + designs.map(d => d.key).join(', '))

const SCORE = {
  type: 'object',
  properties: {
    scores: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          key: { type: 'string' },
          score: { type: 'number' },
          strongest_point: { type: 'string' },
          fatal_or_serious_flaws: { type: 'string' },
          what_to_take_from_it: { type: 'string' },
        },
        required: ['key', 'score', 'strongest_point', 'fatal_or_serious_flaws', 'what_to_take_from_it'],
      },
    },
    ranking: { type: 'string' },
    advice_for_the_final_design: { type: 'string' },
  },
  required: ['scores', 'ranking', 'advice_for_the_final_design'],
}

const LENSES = [
  { key: 'fidelity', text: "YOUR LENS: fidelity to the directive. Does the design improve the acquisition MECHANISM (and is the line between mechanism and learned state real, so that the five arms mean something), or does it relabel task-level learning, caching or parameter tuning as meta-improvement? Is the self-modification proposed by the system from its own experience? Are the domains genuinely external and unseen? Does it answer the Phase P problem or dodge it? Would the success criterion of the directive be observable with it, and could it fail?" },
  { key: 'feasibility', text: "YOUR LENS: feasibility and attribution in this environment. Can it be built in hours and run on 4 CPU cores within about 8 to 12 hours for the registered experiment? Check the designers' arithmetic and their small experiments (rerun one if in doubt, within the rules). Is the base mechanism strong enough on the development puzzles that there is something to measure, and weak enough that there is room? Will the arms isolate what they claim to (mechanism change against retained state against more compute)? Where will the implementation go wrong?" },
  { key: 'rigour', text: "YOUR LENS: verification and the risk of self-deception. What is hidden from the system and is it really hidden? Is the validation that admits a modification independent of the data that proposed it, and is the final test independent of both? Are the statistics sound for the number of puzzles and domains available (130 test puzzles in 12 modules of very unequal size)? Which results would be over-read? What must be pre-registered, and which negative results are the likely ones? Does it preserve reproducibility (seeded determinism, countable budgets, digests) and rollback?" },
]

phase('Judge')
const verdicts = (await parallel(LENSES.map(l => () =>
  agent([RULES, "", "Your work directory: " + WORK + "/judge-" + l.key, "", CONTEXT, "", "You are a judge on a panel. Four designs are below as JSON. " + l.text,
    "Score every design from 0 to 10 under your lens, with its strongest point, its fatal or serious flaws (be specific: quote the design), and what the final design should take from it. Then give a ranking and concrete advice for the final design: what to combine, what to drop, what is missing from all four.", "", "DESIGNS (JSON):", JSON.stringify(designs, null, 1)].join("\n"),
    { label: 'judge:' + l.key, phase: 'Judge', schema: SCORE, model: 'opus' }).then(v => v ? { lens: l.key, ...v } : null)
))).filter(Boolean)

const BLUEPRINT = {
  type: 'object',
  properties: {
    name: { type: 'string' },
    one_paragraph: { type: 'string' },
    mechanism_and_state: { type: 'string' },
    self_modification: { type: 'string' },
    capability_and_hidden_material: { type: 'string' },
    generations_and_arms: { type: 'string' },
    measures_tests_thresholds: { type: 'string' },
    phase_p_answer: { type: 'string' },
    files_and_interfaces: { type: 'string' },
    work_packages: {
      type: 'array',
      items: {
        type: 'object',
        properties: { id: { type: 'string' }, title: { type: 'string' }, files: { type: 'string' }, spec: { type: 'string' }, depends_on: { type: 'string' }, acceptance: { type: 'string' } },
        required: ['id', 'title', 'files', 'spec', 'depends_on', 'acceptance'],
      },
    },
    development_experiments: { type: 'string' },
    registered_run: { type: 'string' },
    predictions_skeleton: { type: 'string' },
    limits: { type: 'string' },
    rejected_alternatives: { type: 'string' },
  },
  required: ['name', 'one_paragraph', 'mechanism_and_state', 'self_modification', 'capability_and_hidden_material', 'generations_and_arms', 'measures_tests_thresholds', 'phase_p_answer', 'files_and_interfaces', 'work_packages', 'development_experiments', 'registered_run', 'predictions_skeleton', 'limits', 'rejected_alternatives'],
}

phase('Synthesize')
const blueprint = await agent([RULES, "", "Your work directory: " + WORK + "/synthesize", "", CONTEXT, "",
  "Four designs and three judges' verdicts are below. Write the ONE blueprint that will be built: take the strongest base design, graft what the judges say is worth taking from the others, and repair every serious flaw the judges named or say why it cannot be repaired. The blueprint must be buildable by several engineers working in parallel on separate files: give exact file names (a new package directory rsi6/ at the repository root), the interfaces between files (function and class signatures with types), and work packages with acceptance tests. Keep it the SMALLEST credible system: cut anything that is not needed to test the directive's question with its five arms. State the pre-registration skeleton (primary comparison, arms, budgets in countable units, tests, thresholds, the predictions to register) and the limits. You may run small checks on the development puzzles within the rules.",
  "", "DESIGNS (JSON):", JSON.stringify(designs, null, 1), "", "VERDICTS (JSON):", JSON.stringify(verdicts, null, 1)].join("\n"),
  { label: 'synthesize', phase: 'Synthesize', schema: BLUEPRINT, model: 'opus' })

const critique = await agent([RULES, "", "Your work directory: " + WORK + "/critic", "", CONTEXT, "",
  "A blueprint for the experiment is below. Attack it before it is built. Find: a place where it does not test the directive's question (meta-level improvement of acquisition, not task-level learning); an arm that does not isolate what it claims; a leak of hidden material; a statistical claim the data cannot carry; a part that cannot be built or run in the stated time; an interface between work packages that is underspecified or contradictory; a likely reason the registered run produces an uninterpretable result. At most 12 points, strongest first, each with the smallest repair.",
  "", "BLUEPRINT (JSON):", JSON.stringify(blueprint, null, 1)].join("\n"),
  { label: 'critic', phase: 'Synthesize', model: 'opus', schema: { type: 'object', properties: { points: { type: 'array', items: { type: 'object', properties: { point: { type: 'string' }, why: { type: 'string' }, repair: { type: 'string' } }, required: ['point', 'why', 'repair'] } } }, required: ['points'] } })

return { designs, verdicts, blueprint, critique }
