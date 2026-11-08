import * as THREE from 'three'
import { mergeGeometries } from 'three/examples/jsm/utils/BufferGeometryUtils.js'

export type WorkerRole = 'picker' | 'packer' | 'receiver' | 'shipper' | 'forklift_driver'
export interface WorkerRoleDefinition { readonly color: string; readonly code: string; readonly icon: string }
export const WORKER_ROLE_DEFINITIONS: Readonly<Record<WorkerRole, WorkerRoleDefinition>> = Object.freeze({
  picker: Object.freeze({ color: '#3478F6', code: '01', icon: 'cart' }),
  packer: Object.freeze({ color: '#F28C28', code: '02', icon: 'carton' }),
  receiver: Object.freeze({ color: '#9B59D0', code: '03', icon: 'incoming_arrow' }),
  shipper: Object.freeze({ color: '#2AA56A', code: '04', icon: 'outgoing_arrow' }),
  forklift_driver: Object.freeze({ color: '#F4C542', code: '05', icon: 'forklift' }),
})
export const WORKER_ROLE_TINT_NAMES = Object.freeze(['V3_Worker_RoleVest', 'V3_Worker_RoleHeadwear'] as const)

export interface WorkerInstance {
  readonly root: THREE.Object3D
  readonly actorId: string
  readonly role: WorkerRole
  readonly disposed: boolean
}
interface InstanceState {
  root: THREE.Object3D
  actorId: string
  initialRole: WorkerRole
  role: WorkerRole
  disposed: boolean
  tints: THREE.MeshStandardMaterial[]
  badge: THREE.Mesh<THREE.BufferGeometry, THREE.Material>
}
const instances = new WeakMap<WorkerInstance, InstanceState>()
type Point = readonly [number, number]

function checkedRole(role: unknown): WorkerRole {
  if (typeof role !== 'string' || !Object.hasOwn(WORKER_ROLE_DEFINITIONS, role)) throw new TypeError(`Unknown worker role: ${String(role)}`)
  return role as WorkerRole
}
function checkedActorId(id: unknown): string {
  if (typeof id !== 'string' || !/^[A-Za-z][A-Za-z0-9_-]{0,63}$/.test(id)) throw new TypeError('actorId must be a stable nonempty alphanumeric identifier, not a role code')
  return id
}
function stateFor(instance: WorkerInstance): InstanceState {
  const state = instances.get(instance)
  if (!state || state.disposed) throw new Error('Worker instance is unknown or disposed')
  return state
}
function sourceParts(mesh: THREE.Mesh): string[] {
  try { return JSON.parse(mesh.userData.source_parts_json ?? '[]') as string[] }
  catch { throw new Error(`Invalid source part metadata on ${mesh.name}`) }
}
function materials(mesh: THREE.Mesh): THREE.Material[] { return Array.isArray(mesh.material) ? mesh.material : [mesh.material] }
function shape(points: readonly Point[]): THREE.Shape {
  const result = new THREE.Shape()
  result.moveTo(...points[0]!)
  for (const p of points.slice(1)) result.lineTo(...p)
  result.closePath()
  return result
}
function rectangle(x0: number, y0: number, x1: number, y1: number): THREE.Shape {
  return shape([[x0, y0], [x1, y0], [x1, y1], [x0, y1]])
}
function disc(x: number, y: number, radius: number): THREE.Shape {
  return shape(Array.from({ length: 10 }, (_, i) => [x + radius * Math.cos(i * Math.PI / 5), y + radius * Math.sin(i * Math.PI / 5)] as Point))
}

// Small vector digits, not an actor-ID texture or external font dependency.
function digit(value: string): THREE.Shape {
  if (value === '0') {
    const outer = shape([[-.009, -.011], [-.006, -.014], [.006, -.014], [.009, -.011], [.009, .011], [.006, .014], [-.006, .014], [-.009, .011]])
    const hole = new THREE.Path()
    hole.moveTo(-.004, -.009); hole.lineTo(-.004, .009); hole.lineTo(.004, .009); hole.lineTo(.004, -.009); hole.closePath()
    outer.holes.push(hole)
    return outer
  }
  const outlines: Record<string, Point[]> = {
    '1': [[-.008, -.014], [.009, -.014], [.009, -.010], [.004, -.010], [.004, .014], [-.001, .014], [-.008, .008], [-.005, .004], [0, .008], [0, -.010], [-.008, -.010]],
    '2': [[-.009, .014], [.009, .014], [.009, .003], [-.004, -.009], [.009, -.009], [.009, -.014], [-.009, -.014], [-.009, -.005], [.004, .007], [.004, .009], [-.009, .009]],
    '3': [[-.009, .014], [.009, .014], [.009, -.014], [-.009, -.014], [-.009, -.009], [.004, -.009], [.004, -.002], [-.005, -.002], [-.005, .003], [.004, .003], [.004, .009], [-.009, .009]],
    '4': [[.003, .014], [.009, .014], [.009, -.014], [.003, -.014], [.003, -.004], [-.009, -.004], [-.009, .014], [-.003, .014], [-.003, .002], [.003, .002]],
    '5': [[-.009, .014], [.009, .014], [.009, .009], [-.004, .009], [-.004, .003], [.009, .003], [.009, -.014], [-.009, -.014], [-.009, -.009], [.004, -.009], [.004, -.002], [-.009, -.002]],
  }
  const points = outlines[value]
  if (!points) throw new Error(`Unsupported role digit ${value}`)
  return shape(points)
}

function buildBadgeGeometry(role: WorkerRole): THREE.BufferGeometry {
  const pieces: THREE.BufferGeometry[] = []
  const add = (s: THREE.Shape, x = 0, y = .017, front = .0105) => {
    const part = new THREE.ExtrudeGeometry(s, { depth: front - .0045, bevelEnabled: false, steps: 1, curveSegments: 2 })
    part.translate(x, y, .0045)
    pieces.push(part)
  }
  if (role === 'picker') {
    add(shape([[-.012, -.006], [.020, -.006], [.026, .012], [-.015, .012]]))
    add(shape([[-.021, .022], [-.014, -.004], [-.009, -.004], [-.016, .022]]), 0, .017, .0100)
    add(rectangle(-.029, .019, -.015, .024), 0, .017, .0110)
    add(disc(-.006, -.012, .004)); add(disc(.018, -.012, .004))
  } else if (role === 'packer') {
    // Three broad carton faces, with white seams supplied by the badge base.
    add(shape([[0, .023], [.023, .012], [0, .002], [-.023, .012]]))
    add(shape([[-.023, .009], [-.0015, -.001], [-.0015, -.022], [-.023, -.012]]))
    add(shape([[.0015, -.001], [.023, .009], [.023, -.012], [.0015, -.022]]))
  } else if (role === 'receiver' || role === 'shipper') {
    add(shape([[-.026, -.016], [.026, -.016], [.026, -.006], [.021, -.006], [.021, -.011], [-.021, -.011], [-.021, -.006], [-.026, -.006]]))
    const arrow: Point[] = [[-.005, .027], [.005, .027], [.005, .008], [.014, .008], [0, -.005], [-.014, .008], [-.005, .008]]
    add(shape(role === 'receiver' ? arrow : arrow.map(([x, y]) => [x, .022 - y] as Point)))
  } else {
    const body = shape([[-.026, -.009], [.014, -.009], [.014, -.014], [.032, -.014], [.032, -.009], [.019, -.009], [.019, .028], [.014, .028], [.014, .005], [.008, .005], [.008, .028], [-.022, .028], [-.022, .006], [-.026, .006]])
    const window = new THREE.Path()
    window.moveTo(-.017, .010); window.lineTo(-.017, .023); window.lineTo(.003, .023); window.lineTo(.003, .010); window.closePath()
    body.holes.push(window)
    add(body)
    add(disc(-.016, -.011, .005)); add(disc(.005, -.011, .005))
  }
  const code = WORKER_ROLE_DEFINITIONS[role].code
  add(digit(code[0]!), -.014, -.027)
  add(digit(code[1]!), .014, -.027)
  const merged = mergeGeometries(pieces, false)
  for (const part of pieces) part.dispose()
  if (!merged) throw new Error('Cannot assemble worker role badge')
  merged.computeBoundingBox(); merged.computeBoundingSphere()
  return merged
}

export function createWorkerInstance(template: THREE.Object3D, actorId: string, role: WorkerRole): WorkerInstance {
  checkedActorId(actorId); checkedRole(role)
  if (!template?.isObject3D) throw new TypeError('A loaded worker Object3D template is required')
  const source = template.name === 'worker_base_root' ? template : template.getObjectByName('worker_base_root')
  if (!source) throw new Error('Template does not contain worker_base_root')
  const root = source.clone(true)
  const tintSources = new Map<string, THREE.MeshStandardMaterial>()
  let badgeBase: THREE.Mesh | undefined, originalInk: THREE.Mesh | undefined
  root.traverse(node => {
    if (!(node instanceof THREE.Mesh)) return
    const parts = sourceParts(node)
    if (parts.includes('role_badge_base')) badgeBase = node
    if (parts.includes('role_badge_cart')) originalInk = node
    for (const mat of materials(node)) if (WORKER_ROLE_TINT_NAMES.some(name => name === mat.name)) {
      if (!(mat instanceof THREE.MeshStandardMaterial)) throw new Error('Role tint requires a standard material')
      tintSources.set(mat.name, mat)
    }
  })
  if (tintSources.size !== 2 || !badgeBase || !originalInk || !badgeBase.parent) throw new Error('Worker template is missing tint/badge interfaces')
  const inkMaterial = materials(originalInk).find(mat => mat.name === 'V3_Worker_BadgeInk')
  if (!inkMaterial) throw new Error('Worker badge ink material is missing')
  const tintClones = new Map([...tintSources].map(([name, mat]) => [name, mat.clone()]))
  root.traverse(node => {
    if (!(node instanceof THREE.Mesh)) return
    const replace = (mat: THREE.Material) => tintClones.get(mat.name) ?? mat
    node.material = Array.isArray(node.material) ? node.material.map(replace) : replace(node.material)
  })
  originalInk.visible = false
  const badge = new THREE.Mesh(buildBadgeGeometry(role), inkMaterial)
  badge.name = 'role_badge__' + actorId
  badge.position.copy(badgeBase.position); badge.quaternion.copy(badgeBase.quaternion); badge.scale.copy(badgeBase.scale)
  badge.userData.roleBadge = true
  badgeBase.parent.add(badge)
  root.name = 'actor__' + actorId
  root.userData.actorId = actorId
  const state: InstanceState = { root, actorId, initialRole: role, role, disposed: false, tints: [...tintClones.values()], badge }
  const instance: WorkerInstance = Object.freeze({ root, actorId, get role() { return state.role }, get disposed() { return state.disposed } })
  instances.set(instance, state)
  setRoleVisuals(state, role)
  return instance
}
function setRoleVisuals(state: InstanceState, role: WorkerRole) {
  const definition = WORKER_ROLE_DEFINITIONS[role]
  for (const mat of state.tints) mat.color.set(definition.color)
  state.role = role
  state.root.userData.workerRole = role
  state.root.userData.roleCode = definition.code
  state.badge.userData.role = role
  state.badge.userData.roleCode = definition.code
  state.badge.userData.icon = definition.icon
  state.badge.userData.actorId = state.actorId
}
export function applyWorkerRole(instance: WorkerInstance, role: WorkerRole): void {
  checkedRole(role)
  const state = stateFor(instance)
  if (state.role === role) return
  const next = buildBadgeGeometry(role)
  state.badge.geometry.dispose()
  state.badge.geometry = next
  setRoleVisuals(state, role)
}
export function resetWorkerRole(instance: WorkerInstance): void {
  const state = stateFor(instance)
  applyWorkerRole(instance, state.initialRole)
}
export function disposeWorkerInstance(instance: WorkerInstance): void {
  const state = instances.get(instance)
  if (!state) throw new Error('Unknown worker instance')
  if (state.disposed) return
  state.disposed = true
  state.badge.geometry.dispose()
  for (const mat of state.tints) mat.dispose()
  state.root.removeFromParent()
  state.root.clear()
}

// Kept as a separate helper so production creation has no QA staffing effects.
export { createWorkerRolesFixture } from './workerRolesFixture'
