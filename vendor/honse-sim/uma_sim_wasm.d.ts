/* tslint:disable */
/* eslint-disable */

/**
 * A streaming race simulator with per-event JS callbacks.
 *
 * Construct with [`WasmRaceSimulator::new`], register callbacks, then call
 * [`run`](WasmRaceSimulator::run) to drive the race aggregate over the
 * configured rounds. Callbacks fire live; the serialized batch result is
 * returned at the end.
 */
export class WasmRaceSimulator {
    free(): void;
    [Symbol.dispose](): void;
    /**
     * Build a simulator from a [`WasmRaceSimParams`] JS object.
     */
    constructor(params: any);
    /**
     * Run the configured rounds, firing callbacks live, and return the
     * serialized [`WasmRaceSimResult`].
     */
    run(): any;
    /**
     * Register the `after-runner-tick(snapshot)` callback.
     */
    setOnAfterRunnerTick(cb: Function): void;
    /**
     * Register the `before-tick(dt)` callback.
     */
    setOnBeforeTick(cb: Function): void;
    /**
     * Register the `round-end()` callback.
     */
    setOnRoundEnd(cb: Function): void;
    /**
     * Register the `round-start(seed)` callback.
     */
    setOnRoundStart(cb: Function): void;
    /**
     * Register the `runner-finished(runnerId)` callback.
     */
    setOnRunnerFinished(cb: Function): void;
}

/**
 * Validate every supplied condition and precondition before a race can silently
 * discard a malformed branch. Does not claim the condition's semantics match
 * the native game.
 */
export function conditionSupportReport(skills: any): any;

/**
 * The late-race HP consumption multiplier for a guts stat.
 *
 * See [`honse_sim::readouts::guts_hp_burn_multiplier`].
 */
export function gutsHpBurnMultiplier(guts: number): number;

/**
 * Stamina's HP conversion coefficient for a strategy id (1-5).
 *
 * See [`honse_sim::readouts::hp_strategy_coefficient`].
 */
export function hpStrategyCoefficient(strategy: number): number;

/**
 * All condition tokens the Rust engine's catalog recognizes.
 *
 * Exposed so an external consumer can cross-check its simulatability gate
 * against the engine that runs the simulation. Any token a consumer treats as
 * simulatable must be resolvable by this engine.
 * Returned as a sorted JS string array.
 */
export function knownConditionTokens(): string[];

/**
 * The HP a runner starts a race with, from stamina, strategy id, and course
 * distance in meters.
 *
 * See [`honse_sim::readouts::max_hp`].
 */
export function maxHp(stamina: number, strategy: number, distance: number): number;

/**
 * Run a batch compare-family simulation and return the serialized result.
 *
 * `params` is a [`WasmCompareParams`] JS object (a small vacuum field over
 * `nsamples` rounds). Returns a [`WasmCompareData`] (per-round, per-runner
 * telemetry); the bashin-delta + summary stats are computed on the TS side.
 */
export function runCompare(params: any): any;

/**
 * Run a same-race compare-family simulation and return the serialized result.
 *
 * `params` is a [`WasmContestedCompareParams`] JS object (2..=12 compared
 * runners, optionally mob-filled via `fillTo`). Returns the same [`WasmCompareData`] shape
 * as vacuum compare so the TS reducer can be reused.
 */
export function runContestedCompare(params: any): any;

/**
 * Run a batch race simulation and return the serialized result.
 *
 * `params` is a [`WasmRaceSimParams`] JS object. Returns a
 * [`WasmRaceSimResult`] (per-round finish orders + focus telemetry).
 */
export function runRaceSim(params: any): any;

/**
 * The pre-race wisdom check pass rate, as a percentage, for a base wit stat.
 *
 * See [`honse_sim::readouts::skill_activation_percent`].
 */
export function skillActivationPercent(base_wit: number): number;

/**
 * Which of the submitted skills this engine models only partially.
 *
 * `skills` is an array of the same skill objects a simulation takes. Returns one
 * entry per skill that loses at least one effect, each listing the dropped
 * effects and whether the skill is left inert; a fully modeled skill is omitted,
 * so an empty array means full coverage.
 *
 * The engine drops effects it cannot model rather than rejecting the skill —
 * an unmapped effect `type` (what it does), `valueUsage` (how much), or `target`
 * (who receives it), or a tiered usage that did not state the
 * `preAppliedMultiplier` already folded into its modifier — so a simulation
 * always runs, but a dropped effect makes that skill's contribution understated.
 * Exposed so a consumer can say which skills are affected instead of presenting
 * partial results as complete.
 *
 * The answer is a property of the skill data alone, so call it once per skill
 * pool rather than per simulation. It accepts a whole pool: no unmapped code in
 * any submitted skill can make this throw.
 */
export function skillSupportReport(skills: any): any;

export type InitInput = RequestInfo | URL | Response | BufferSource | WebAssembly.Module;

export interface InitOutput {
    readonly memory: WebAssembly.Memory;
    readonly __wbg_wasmracesimulator_free: (a: number, b: number) => void;
    readonly conditionSupportReport: (a: any) => [number, number, number];
    readonly hpStrategyCoefficient: (a: number) => [number, number, number];
    readonly knownConditionTokens: () => [number, number];
    readonly maxHp: (a: number, b: number, c: number) => [number, number, number];
    readonly runCompare: (a: any) => [number, number, number];
    readonly runContestedCompare: (a: any) => [number, number, number];
    readonly runRaceSim: (a: any) => [number, number, number];
    readonly skillSupportReport: (a: any) => [number, number, number];
    readonly wasmracesimulator_new: (a: any) => [number, number, number];
    readonly wasmracesimulator_run: (a: number) => [number, number, number];
    readonly wasmracesimulator_setOnAfterRunnerTick: (a: number, b: any) => void;
    readonly wasmracesimulator_setOnBeforeTick: (a: number, b: any) => void;
    readonly wasmracesimulator_setOnRoundEnd: (a: number, b: any) => void;
    readonly wasmracesimulator_setOnRoundStart: (a: number, b: any) => void;
    readonly wasmracesimulator_setOnRunnerFinished: (a: number, b: any) => void;
    readonly gutsHpBurnMultiplier: (a: number) => number;
    readonly skillActivationPercent: (a: number) => number;
    readonly __wbindgen_malloc: (a: number, b: number) => number;
    readonly __wbindgen_realloc: (a: number, b: number, c: number, d: number) => number;
    readonly __wbindgen_exn_store: (a: number) => void;
    readonly __externref_table_alloc: () => number;
    readonly __wbindgen_externrefs: WebAssembly.Table;
    readonly __externref_table_dealloc: (a: number) => void;
    readonly __externref_drop_slice: (a: number, b: number) => void;
    readonly __wbindgen_free: (a: number, b: number, c: number) => void;
    readonly __wbindgen_start: () => void;
}

export type SyncInitInput = BufferSource | WebAssembly.Module;

/**
 * Instantiates the given `module`, which can either be bytes or
 * a precompiled `WebAssembly.Module`.
 *
 * @param {{ module: SyncInitInput }} module - Passing `SyncInitInput` directly is deprecated.
 *
 * @returns {InitOutput}
 */
export function initSync(module: { module: SyncInitInput } | SyncInitInput): InitOutput;

/**
 * If `module_or_path` is {RequestInfo} or {URL}, makes a request and
 * for everything else, calls `WebAssembly.instantiate` directly.
 *
 * @param {{ module_or_path: InitInput | Promise<InitInput> }} module_or_path - Passing `InitInput` directly is deprecated.
 *
 * @returns {Promise<InitOutput>}
 */
export default function __wbg_init (module_or_path?: { module_or_path: InitInput | Promise<InitInput> } | InitInput | Promise<InitInput>): Promise<InitOutput>;
