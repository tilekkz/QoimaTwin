import type { MotionPose, VisualActor, Vec3 } from './types';

const seed = (id: string) => [...id].reduce((n, c) => (n * 31 + c.charCodeAt(0)) % 997, 0) / 997 * Math.PI * 2;

/** Cosmetic bind-relative Euler XYZ, runtime Y-up; never changes logical position. */
export function proceduralPose(actor: Omit<VisualActor, 'pose'>, time: number, reducedMotion = false): MotionPose {
  const jointRotations: Record<string, Vec3> = {};
  const result: MotionPose = { jointRotations, rootOffset: [0, 0, 0], wheelAngle: 0, lift: actor.role === 'forklift_driver' && actor.entityId ? .171 : 0 };
  if (actor.role === 'forklift_driver' && actor.operation === 'loading') result.lift = Math.min(1, Math.max(0, (actor.phase - .8) / .2)) * .171;
  if (actor.role === 'forklift_driver' && actor.operation === 'unloading') result.lift = (1 - Math.min(1, Math.max(0, (actor.phase - .8) / .2))) * .171;
  if (reducedMotion) return result;
  const phase = seed(actor.id);
  const service = actor.state === 'BUSY_SERVICE';
  if (actor.operation === 'pallet_place' || actor.operation === 'placement_return') {
    const lower = actor.operation === 'pallet_place' ? actor.phase : 1 - actor.phase;
    jointRotations.torso = [1.57 * lower, 0, 0];
    for (const side of ['L', 'R']) { jointRotations['upper_arm_' + side] = [-.58 - .895 * lower, 0, (side === 'L' ? -.05 : .05)]; jointRotations['forearm_' + side] = [-.22 - .18 * lower, 0, 0]; }
    return result;
  }
  if (['handoff', 'tote_wait', 'handoff_return'].includes(actor.operation)) {
    const moving = actor.operation === 'handoff' ? Math.max(0, Math.min(1, (actor.phase - .1) / .9)) : 1;
    const reach = actor.operation === 'handoff' ? Math.min(1, actor.phase / .1) : actor.operation === 'tote_wait' ? 1 - .2 * actor.phase : .8 * (1 - actor.phase);
    const keys = [[0, .8, -.375, -.35], [.4, .75, -.725, -.525], [.8, 1.025, -1.5, -.825], [1, .95, -1.9, -.025]];
    const index = Math.min(keys.length - 2, Math.max(0, keys.findIndex((key, i) => i < keys.length - 1 && moving >= key[0] && moving <= keys[i + 1][0])));
    const a = keys[index], b = keys[index + 1], blend = (moving - a[0]) / (b[0] - a[0]);
    const angles = a.slice(1).map((v, i) => (v + (b[i + 1] - v) * blend) * reach);
    jointRotations.torso = [angles[0], 0, 0];
    for (const side of ['L', 'R']) { jointRotations['upper_arm_' + side] = [angles[1], 0, (side === 'L' ? -.13 : .13) * reach]; jointRotations['forearm_' + side] = [angles[2], 0, 0]; }
    result.rootOffset[0] = Math.sin(actor.yaw) * .05 * moving * reach;
    result.rootOffset[2] = Math.cos(actor.yaw) * .05 * moving * reach;
    return result;
  }
  if (actor.state === 'TRAVEL') {
    if (actor.role === 'forklift_driver') {
      jointRotations.head = [0, .07 * Math.sin(time * .8 + phase), 0];
      result.wheelAngle = time * 5;
      return result;
    }
    const gait = Math.sin(time * 7.4 + phase);
    jointRotations.thigh_L = [.32 * gait, 0, 0];
    jointRotations.thigh_R = [-.32 * gait, 0, 0];
    jointRotations.shin_L = [Math.max(0, -.36 * gait), 0, 0];
    jointRotations.shin_R = [Math.max(0, .36 * gait), 0, 0];
    if (actor.entityId && actor.role !== 'picker') {
      jointRotations.upper_arm_L = [-.58, 0, -.05]; jointRotations.upper_arm_R = [-.58, 0, .05];
      jointRotations.forearm_L = [-.22, 0, 0]; jointRotations.forearm_R = [-.22, 0, 0];
    } else if (actor.role !== 'picker') {
      jointRotations.upper_arm_L = [-.2 * gait, 0, 0];
      jointRotations.upper_arm_R = [.2 * gait, 0, 0];
    }
    result.rootOffset[1] = .008 * Math.abs(gait);
    result.wheelAngle = time * 13;
  } else if (service) {
    const work = Math.sin(actor.phase * Math.PI);
    const cycle = Math.sin(time * 3 + phase);
    if (actor.operation === 'pick') {
      // Cosmetic reach in world coordinates; logical graph position stays fixed.
      result.rootOffset[0] = Math.sin(actor.yaw) * .55 * work;
      result.rootOffset[2] = Math.cos(actor.yaw) * .55 * work;
      jointRotations.torso = [1.35 * work, 0, 0];
      jointRotations.upper_arm_L = [-1.18 * work, 0, 0];
      jointRotations.forearm_L = [-.48 * work, 0, 0];
    } else if (actor.operation === 'pack') {
      const settle = Math.min(1, actor.phase * 30, (1 - actor.phase) * 30);
      result.rootOffset = [.2 * settle, 0, -.12 * settle];
      jointRotations.torso = [.4 * settle, 0, 0];
      jointRotations.upper_arm_L = [(-1.1 + .012 * cycle) * settle, 0, -.025 * settle];
      jointRotations.upper_arm_R = [(-1.1 - .012 * cycle) * settle, 0, .025 * settle];
      jointRotations.forearm_L = [(-.35 + .018 * cycle) * settle, 0, 0];
      jointRotations.forearm_R = [(-.35 - .018 * cycle) * settle, 0, 0];
      jointRotations.head = [.08 * settle, 0, 0];
    } else if (actor.role !== 'forklift_driver') {
      const base = actor.role === 'picker' ? -.1 : -.58;
      jointRotations.upper_arm_L = [base + .06 * cycle, 0, -.05];
      jointRotations.upper_arm_R = [base - .06 * cycle, 0, .05];
      jointRotations.forearm_L = [-.22 + .08 * cycle, 0, 0];
      jointRotations.forearm_R = [-.22 - .08 * cycle, 0, 0];
      jointRotations.head = [.07 * work, 0, 0];
    }
  } else {
    jointRotations.head = [0, .035 * Math.sin(time * .35 + phase), 0];
    result.rootOffset[1] = .0015 * Math.sin(time * 1.5 + phase);
  }
  return result;
}
