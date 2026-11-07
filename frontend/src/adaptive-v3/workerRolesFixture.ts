import * as THREE from 'three'
import { createWorkerInstance, disposeWorkerInstance, resetWorkerRole, type WorkerInstance, type WorkerRole } from './workerRoles'

export interface WorkerRolesFixture {
  readonly root: THREE.Group
  readonly instances: readonly WorkerInstance[]
  reset(): void
  dispose(): void
}

/** Five representative QA actors, not a new production staffing population. */
export function createWorkerRolesFixture(template: THREE.Object3D): WorkerRolesFixture {
  const root = new THREE.Group()
  root.name = 'qa_worker_roles'
  root.userData.qaFixture = 'five-role visual comparison; canonical staffing remains24'
  const roles: readonly [string, WorkerRole][] = [
    ['P01', 'picker'], ['K01', 'packer'], ['R01', 'receiver'], ['S01', 'shipper'], ['F01', 'forklift_driver'],
  ]
  const instances: WorkerInstance[] = []
  try {
    for (const [index, [actorId, role]] of roles.entries()) {
      const instance = createWorkerInstance(template, actorId, role)
      instance.root.position.x = (index - 2) * 1.1
      root.add(instance.root)
      instances.push(instance)
    }
  } catch (error) {
    for (const instance of instances) disposeWorkerInstance(instance)
    throw error
  }
  let disposed = false
  return Object.freeze({
    root,
    instances: Object.freeze(instances),
    reset() {
      if (disposed) throw new Error('Role fixture is disposed')
      for (const instance of instances) resetWorkerRole(instance)
    },
    dispose() {
      if (disposed) return
      disposed = true
      for (const instance of instances) disposeWorkerInstance(instance)
      root.removeFromParent()
      root.clear()
    },
  })
}
