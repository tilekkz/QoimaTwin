"""Small independent GLB triangle reader for physical interface verification."""
from __future__ import annotations

import json
import math
from pathlib import Path
import struct


def add(a, b):
    return tuple(x + y for x, y in zip(a, b))


def sub(a, b):
    return tuple(x - y for x, y in zip(a, b))


def mul(a, s):
    return tuple(x * s for x in a)


def dot(a, b):
    return sum(x * y for x, y in zip(a, b))


def distance(a, b):
    return math.sqrt(dot(sub(a, b), sub(a, b)))


def closest(p, tri):
    """Closest point on a finite triangle, including its edges and vertices."""
    a, b, c = tri
    ab, ac, ap = sub(b, a), sub(c, a), sub(p, a)
    d1, d2 = dot(ab, ap), dot(ac, ap)
    if d1 <= 0 and d2 <= 0:
        return a
    bp = sub(p, b)
    d3, d4 = dot(ab, bp), dot(ac, bp)
    if d3 >= 0 and d4 <= d3:
        return b
    vc = d1 * d4 - d3 * d2
    if vc <= 0 and d1 >= 0 and d3 <= 0:
        return add(a, mul(ab, d1 / (d1 - d3)))
    cp = sub(p, c)
    d5, d6 = dot(ab, cp), dot(ac, cp)
    if d6 >= 0 and d5 <= d6:
        return c
    vb = d5 * d2 - d1 * d6
    if vb <= 0 and d2 >= 0 and d6 <= 0:
        return add(a, mul(ac, d2 / (d2 - d6)))
    va = d3 * d6 - d5 * d4
    if va <= 0 and d4 - d3 >= 0 and d5 - d6 >= 0:
        return add(b, mul(sub(c, b), (d4 - d3) / (d4 - d3 + d5 - d6)))
    denominator = va + vb + vc
    if abs(denominator) <= 1e-30:
        raise ValueError('Degenerate native triangle')
    return add(a, add(mul(ab, vb / denominator), mul(ac, vc / denominator)))


def normal(tri):
    a, b = sub(tri[1], tri[0]), sub(tri[2], tri[0])
    cross = (a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0])
    length = math.sqrt(dot(cross, cross))
    if length <= 1e-20:
        raise ValueError('Degenerate native triangle')
    return mul(cross, 1 / length)


IDENTITY = ((1,0,0,0),(0,1,0,0),(0,0,1,0),(0,0,0,1))


def product(a, b):
    return tuple(tuple(sum(a[i][k]*b[k][j] for k in range(4)) for j in range(4)) for i in range(4))


def transform(m, p):
    return tuple(sum(m[i][j]*p[j] for j in range(3)) + m[i][3] for i in range(3))


def local_matrix(node):
    if 'matrix' in node:
        return tuple(tuple(node['matrix'][j*4+i] for j in range(4)) for i in range(4))
    x,y,z,w = node.get('rotation', (0,0,0,1))
    sx,sy,sz = node.get('scale', (1,1,1))
    tx,ty,tz = node.get('translation', (0,0,0))
    # Retain source Float32 quaternion values as the actual renderer does.
    return (( (1-2*(y*y+z*z))*sx, 2*(x*y-z*w)*sy, 2*(x*z+y*w)*sz, tx),
            (2*(x*y+z*w)*sx, (1-2*(x*x+z*z))*sy, 2*(y*z-x*w)*sz, ty),
            (2*(x*z-y*w)*sx, 2*(y*z+x*w)*sy, (1-2*(x*x+y*y))*sz, tz),
            (0,0,0,1))


class GLB:
    def __init__(self, path: Path):
        raw = path.read_bytes()
        if raw[:4] != b'glTF' or struct.unpack_from('<I', raw, 4)[0] != 2:
            raise ValueError('GLB2 source required')
        if struct.unpack_from('<I', raw, 8)[0] != len(raw):
            raise ValueError('GLB length mismatch')
        offset, document, binary = 12, None, None
        while offset < len(raw):
            size, kind = struct.unpack_from('<II', raw, offset)
            block = raw[offset+8:offset+8+size]
            if kind == 0x4E4F534A:
                document = json.loads(block)
            elif kind == 0x004E4942:
                binary = block
            offset += 8 + size
        if document is None or binary is None:
            raise ValueError('Native JSON/BIN chunks required')
        self.doc, self.binary, self.accessors, self.world = document, binary, {}, {}
        self.names = {n.get('name'): i for i,n in enumerate(document['nodes'])}
        parents = {}
        for i,node in enumerate(document['nodes']):
            for child in node.get('children', []):
                if child in parents:
                    raise ValueError('Multiple native parents')
                parents[child] = i
        def world(i):
            if i not in self.world:
                self.world[i] = product(world(parents[i]), local_matrix(document['nodes'][i])) if i in parents else local_matrix(document['nodes'][i])
            return self.world[i]
        for i in range(len(document['nodes'])):
            world(i)

    def accessor(self, index):
        if index not in self.accessors:
            a = self.doc['accessors'][index]
            if 'sparse' in a or a.get('normalized'):
                raise ValueError('Unsupported native accessor representation')
            view = self.doc['bufferViews'][a['bufferView']]
            kind, width = {5121:('B',1),5123:('H',2),5125:('I',4),5126:('f',4)}[a['componentType']]
            n = {'SCALAR':1,'VEC2':2,'VEC3':3,'VEC4':4,'MAT4':16}[a['type']]
            start = view.get('byteOffset', 0) + a.get('byteOffset', 0)
            stride = view.get('byteStride', n * width)
            self.accessors[index] = [struct.unpack_from('<'+kind*n, self.binary, start+i*stride) for i in range(a['count'])]
        return self.accessors[index]

    def triangle(self, node, triangle, primitive=0):
        index = self.names[node] if isinstance(node, str) else node
        part = self.doc['meshes'][self.doc['nodes'][index]['mesh']]['primitives'][primitive]
        if part.get('mode',4) != 4:
            raise ValueError('Native triangle primitive required')
        positions = self.accessor(part['attributes']['POSITION'])
        indices = self.accessor(part['indices']) if 'indices' in part else [(i,) for i in range(len(positions))]
        return tuple(transform(self.world[index], positions[indices[triangle*3+j][0]]) for j in range(3))
