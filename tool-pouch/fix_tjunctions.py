"""Make an OpenSCAD STL watertight by splitting faces at T-vertices.

OpenSCAD 2021 exports faces whose edges pass through vertices of neighbouring
faces (T-junctions).  Slicers repair this silently, but a clean mesh is nicer.
Usage: python3 fix_tjunctions.py in.stl out.stl [out.3mf]
"""
import sys, numpy as np, trimesh

def fix(mesh, tol=1e-3, rounds=6):
    for _ in range(rounds):
        mesh.merge_vertices()
        V, F = mesh.vertices.copy(), mesh.faces.copy()
        edges = mesh.edges_sorted
        groups = trimesh.grouping.group_rows(edges, require_count=1)
        if len(groups) == 0:
            return mesh
        boundary = set(map(tuple, edges[groups]))
        new_faces = []
        for fi, f in enumerate(F):
            pieces = [tuple(f)]
            for k in range(3):
                a, b = f[k], f[(k + 1) % 3]
                if (min(a, b), max(a, b)) not in boundary:
                    continue
                pa, pb = V[a], V[b]
                d = pb - pa; L = np.linalg.norm(d); d /= L
                rel = V - pa
                t = rel @ d
                cand = np.where((t > tol) & (t < L - tol))[0]
                if len(cand) == 0:
                    continue
                perp = np.linalg.norm(rel[cand] - np.outer(t[cand], d), axis=1)
                on = cand[perp < tol]
                on = on[(on != a) & (on != b)]
                if len(on) == 0:
                    continue
                on = on[np.argsort(t[on])]
                # split every piece that still contains edge a-b
                out = []
                for p in pieces:
                    p = list(p)
                    if a in p and b in p:
                        c = [x for x in p if x not in (a, b)][0]
                        chain = [a, *on, b]
                        # keep orientation of the original piece
                        ia, ib = p.index(a), p.index(b)
                        forward = (ib - ia) % 3 == 1
                        for u, v in zip(chain[:-1], chain[1:]):
                            out.append((u, v, c) if forward else (v, u, c))
                    else:
                        out.append(tuple(p))
                pieces = out
            new_faces.extend(pieces)
        mesh = trimesh.Trimesh(V, np.array(new_faces), process=True)
        mesh.update_faces(mesh.nondegenerate_faces())
        mesh = drop_coincident_faces(mesh)
    return mesh

def drop_coincident_faces(mesh):
    """Two faces on the same three vertices are a zero-thickness sheet: remove both."""
    key = np.sort(mesh.faces, axis=1)
    _, inv, cnt = np.unique(key, axis=0, return_inverse=True, return_counts=True)
    keep = cnt[inv.ravel()] == 1
    if keep.all():
        return mesh
    m = trimesh.Trimesh(mesh.vertices, mesh.faces[keep], process=True)
    m.remove_unreferenced_vertices()
    return m

if __name__ == "__main__":
    src, dst = sys.argv[1], sys.argv[2]
    m = trimesh.load(src, process=True)
    v0 = m.volume
    m = drop_coincident_faces(m)
    m = fix(m)
    m = drop_coincident_faces(m)
    _, counts = np.unique(m.edges_sorted, axis=0, return_counts=True)
    open_edges = int((counts == 1).sum())
    pinch_edges = int((counts == 4).sum())
    closed = open_edges == 0 and (counts % 2 == 0).all() and m.is_winding_consistent
    print(f"faces {len(m.faces)}  closed {closed}  open edges {open_edges}  pinch edges {pinch_edges}  "
          f"volume {v0/1000:.1f} -> {m.volume/1000:.1f} cm3")
    if pinch_edges:
        print("note: pinch edges are where two shell layers touch along a line; the volume is "
              "closed and slicers handle them.")
    if not closed:
        sys.exit("mesh has holes")
    m.export(dst)
    for extra in sys.argv[3:]:
        m.export(extra)
