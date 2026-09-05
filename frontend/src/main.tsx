import { Canvas } from '@react-three/fiber';
import { Grid, OrbitControls } from '@react-three/drei';
import { useEffect, useMemo, useRef, useState } from 'react';
import * as THREE from 'three';
import { Design, bounds, clone, levelCenter, moveLevelZ, remapBounds, snap, translateLevel } from './model';
import './styles.css';

type Drag = { type: 'point' | 'front' | 'side' | 'entrance'; handle: number | string; before: Design } | null;
type CameraMode = 'iso' | 'top' | 'front' | 'side';
type ExportNotice = { kind: 'success' | 'failure'; code: string; message: string; files?: string[] };
type ExportResult = { stl: string; step: string; views: string[]; textured_stl?: string; structural_step?: string };
type ErrorPayload = { detail?: { code?: string; message?: string } | string };
const palette = ['#54798b', '#4a8d8b', '#70a46d', '#baab60', '#c98254', '#ba614c', '#9a5464', '#705b85'];

const api = async <T,>(path: string, body?: unknown): Promise<T> => {
  const response = await fetch(path, body === undefined ? undefined : { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
  if (!response.ok) {
    const payload = await response.json().catch(() => ({})) as ErrorPayload;
    const detail = payload.detail;
    const error = new Error(typeof detail === 'object' ? detail.message || response.statusText : detail || response.statusText) as Error & { code?: string };
    error.code = typeof detail === 'object' ? detail.code : undefined;
    throw error;
  }
  return response.json() as Promise<T>;
};
const extent = (design: Design, axis: number) => bounds(design.levels.flatMap((level) => level.points), axis);
const viewBox = (design: Design, axes: [number, number]) => {
  const [minX, maxX] = extent(design, axes[0]);
  const yValues = axes[1] === 2 ? design.levels.map((level) => level.z) : design.levels.flatMap((level) => level.points.map((point) => point[axes[1]]));
  const minY = Math.min(...yValues), maxY = Math.max(...yValues), margin = Math.max(maxX - minX, maxY - minY) * .12 + 5;
  return `${minX - margin} ${-(maxY + margin)} ${maxX - minX + margin * 2} ${maxY - minY + margin * 2}`;
};
const pointer = (event: React.PointerEvent<SVGSVGElement>) => {
  const svg = event.currentTarget; const point = svg.createSVGPoint(); point.x = event.clientX; point.y = event.clientY;
  const transformed = point.matrixTransform(svg.getScreenCTM()!.inverse()); return [transformed.x, -transformed.y];
};

function Preview({ design, selected, camera }: { design: Design; selected: number; camera: CameraMode }) {
  const geometry = useMemo(() => {
    const count = design.levels[0].points.length;
    const positions: number[] = [], colors: number[] = [], indices: number[] = [];
    design.levels.forEach((level, index) => level.points.forEach(([x, y]) => { positions.push(x, y, level.z); const color = new THREE.Color(index === selected ? '#efc06b' : '#577b76'); colors.push(color.r, color.g, color.b); }));
    for (let level = 0; level < design.levels.length - 1; level++) for (let point = 0; point < count; point++) {
      const next = (point + 1) % count, base = level * count, above = base + count;
      indices.push(base + point, base + next, above + point, base + next, above + next, above + point);
    }
    const topCenter = positions.length / 3; const top = design.levels.length - 1;
    const cx = design.levels[top].points.reduce((sum, point) => sum + point[0], 0) / count, cy = design.levels[top].points.reduce((sum, point) => sum + point[1], 0) / count;
    positions.push(cx, cy, design.height); colors.push(.34, .48, .44);
    for (let point = 0; point < count; point++) indices.push(topCenter, top * count + point, top * count + (point + 1) % count);
    const mesh = new THREE.BufferGeometry(); mesh.setAttribute('position', new THREE.Float32BufferAttribute(positions, 3)); mesh.setAttribute('color', new THREE.Float32BufferAttribute(colors, 3)); mesh.setIndex(indices); mesh.computeVertexNormals(); return mesh;
  }, [design, selected]);
  const position: [number, number, number] = camera === 'top' ? [0, 0, 230] : camera === 'front' ? [0, -260, 40] : camera === 'side' ? [260, 0, 40] : [185, -215, 145];
  return <Canvas camera={{ position, fov: 42 }}><color attach="background" args={['#121916']} /><ambientLight intensity={1.3}/><directionalLight position={[-100, -120, 180]} intensity={2}/><mesh geometry={geometry}><meshStandardMaterial vertexColors roughness={.86} metalness={.02} side={THREE.DoubleSide}/></mesh><Grid args={[400, 400]} cellSize={10} sectionSize={50} cellColor="#2d443d" sectionColor="#42574e" position={[0,0,0]}/><OrbitControls makeDefault target={[0, 0, 35]} /></Canvas>;
}

function TopView({ design, selected, drag, setDrag, update, commit, grid }: { design: Design; selected: number; drag: Drag; setDrag: (drag: Drag) => void; update: (fn: (copy: Design) => void) => void; commit: (before: Design) => void; grid: number }) {
  const selectedLevel = design.levels[selected];
  return <Panel title="TOP VIEW" subtitle="XY canonical control loops"><svg viewBox={viewBox(design, [0, 1])} onPointerMove={(event) => { if (drag?.type !== 'point') return; const [x,y] = pointer(event); update((copy) => { copy.levels[selected].points[Number(drag.handle)] = [snap(x,grid), snap(y,grid)]; copy.levels[selected].manually_modified = true; }); }} onPointerUp={() => { if (drag) { commit(drag.before); setDrag(null); } }}>
    <g transform="scale(1,-1)"><GridLines design={design}/>{design.levels.map((level,index) => <polyline key={index} points={[...level.points, level.points[0]].map((point) => point.join(',')).join(' ')} className={index === selected ? 'ring selected' : 'ring'} stroke={palette[index % palette.length]}/>) }<line className="entrance-direction" x1={design.entrance.offset} x2={design.entrance.offset} y1={extent(design, 1)[0] - 9} y2={extent(design, 1)[0] + 9}/>{selectedLevel.points.map((point,index) => <circle key={index} className="control" cx={point[0]} cy={point[1]} r="2.8" onPointerDown={(event) => { event.currentTarget.setPointerCapture(event.pointerId); setDrag({type:'point', handle:index, before:clone(design)}); }}/>)}</g>
  </svg></Panel>;
}

function EnvelopeView({ design, selected, axis, drag, setDrag, update, commit, grid }: { design: Design; selected: number; axis: 0 | 1; drag: Drag; setDrag: (drag: Drag) => void; update: (fn: (copy: Design) => void) => void; commit: (before: Design) => void; grid: number }) {
  const isFront = axis === 0, level = design.levels[selected], [lower, upper] = bounds(level.points, axis), center = (lower + upper) / 2;
  const handles = [[lower, level.z, 'lower'], [upper, level.z, 'upper'], [center, level.z, 'center'], [center, level.z, 'z']] as const;
  return <Panel title={isFront ? 'FRONT VIEW' : 'SIDE VIEW'} subtitle={isFront ? 'X–Z envelope and cave entrance' : 'Y–Z envelope'}>
    <svg viewBox={viewBox(design, [axis, 2])} onPointerMove={(event) => {
      if (!drag || (!isFront && drag.type !== 'side') || (isFront && !['front', 'entrance'].includes(drag.type))) return;
      const [value, z] = pointer(event);
      update((copy) => {
        if (drag.type === 'entrance') {
          copy.entrance.profile[Number(drag.handle)] = [snap(value - copy.entrance.offset, grid), Math.max(0, snap(z, grid))];
          copy.entrance.width = Math.abs(copy.entrance.profile.at(-1)![0] - copy.entrance.profile[0][0]);
          copy.entrance.height = Math.max(...copy.entrance.profile.map((point) => point[1]));
          return;
        }
        const current = copy.levels[selected];
        const [min, max] = bounds(current.points, axis);
        const valueSnapped = snap(value, grid);
        if (drag.handle === 'lower') remapBounds(copy, selected, axis, valueSnapped, max);
        else if (drag.handle === 'upper') remapBounds(copy, selected, axis, min, valueSnapped);
        else if (drag.handle === 'center') translateLevel(copy, selected, axis, valueSnapped);
        else moveLevelZ(copy, selected, snap(z, grid));
      });
    }} onPointerUp={() => { if (drag) { commit(drag.before); setDrag(null); } }}>
      <g transform="scale(1,-1)">
        <GridLines design={design}/>
        <polyline className="envelope" points={design.levels.map((item) => `${bounds(item.points, axis)[0]},${item.z}`).join(' ')}/>
        <polyline className="envelope" points={[...design.levels].reverse().map((item) => `${bounds(item.points, axis)[1]},${item.z}`).join(' ')}/>
        {isFront && <>
          <polyline className="entrance" points={design.entrance.profile.map(([x, entranceZ]) => `${x + design.entrance.offset},${entranceZ}`).join(' ')}/>
          {design.entrance.profile.map(([x, entranceZ], index) => <circle key={index} className="entrance-control" cx={x + design.entrance.offset} cy={entranceZ} r="2.8" onPointerDown={(event) => {
            event.currentTarget.setPointerCapture(event.pointerId);
            setDrag({ type: 'entrance', handle: index, before: clone(design) });
          }}/>)}
        </>}
        <line className="selected-span" x1={lower} x2={upper} y1={level.z} y2={level.z}/>
        {handles.map(([x, handleZ, name]) => <circle key={name} className={`handle ${name}`} cx={x} cy={handleZ} r="3.3" onPointerDown={(event) => {
          event.currentTarget.setPointerCapture(event.pointerId);
          setDrag({ type: isFront ? 'front' : 'side', handle: name, before: clone(design) });
        }}/>)}
      </g>
    </svg>
    {isFront && <EntranceEditor design={design} update={update}/>}
  </Panel>;
}

function EntranceEditor({ design, update }: { design: Design; update: (fn: (copy: Design) => void) => void }) {
  return <div className="entrance-editor">
    <span>Entrance: drag the gold arch handles in Front View.</span>
    <div className="entrance-dimensions">
      <label>Offset <input type="number" value={design.entrance.offset} onChange={(event) => update((copy) => { copy.entrance.offset = Number(event.target.value); })}/></label>
      <label>Width <input type="number" value={design.entrance.width} onChange={(event) => update((copy) => {
        const width = Number(event.target.value);
        if (width <= 0) return;
        const scale = width / copy.entrance.width;
        copy.entrance.profile.forEach((point) => { point[0] *= scale; });
        copy.entrance.width = width;
      })}/></label>
      <label>Height <input type="number" value={design.entrance.height} onChange={(event) => update((copy) => {
        const height = Number(event.target.value);
        if (height <= 0) return;
        const scale = height / copy.entrance.height;
        copy.entrance.profile.forEach((point) => { point[1] *= scale; });
        copy.entrance.height = height;
      })}/></label>
    </div>
  </div>;
}

function GridLines({ design }: { design: Design }) { const [x0,x1] = extent(design,0), [y0,y1] = extent(design,1); return <g className="grid-lines">{Array.from({length: 15},(_,index) => { const x=x0+(x1-x0)*index/14, y=y0+(y1-y0)*index/14; return <g key={index}><line x1={x} x2={x} y1={y0-15} y2={y1+15}/><line x1={x0-15} x2={x1+15} y1={y} y2={y}/></g>; })}</g>; }
function Panel({ title, subtitle, children }: { title: string; subtitle: string; children: React.ReactNode }) { return <section className="panel"><header><strong>{title}</strong><span>{subtitle}</span></header>{children}</section>; }

function ExportDialog({ notice, close }: { notice: ExportNotice; close: () => void }) {
  const title = notice.kind === 'success' ? 'Export completed' : 'Export failed';
  return <div className="export-dialog-backdrop" role="presentation">
    <section className={`export-dialog ${notice.kind}`} role="alertdialog" aria-modal="true" aria-labelledby="export-dialog-title">
      <header>
        <strong id="export-dialog-title">{title}</strong>
        <span>{notice.code}</span>
      </header>
      <p>{notice.message}</p>
      {notice.files && <ul>{notice.files.map((file) => <li key={file}>{file}</li>)}</ul>}
      <button autoFocus onClick={close}>Close</button>
    </section>
  </div>;
}


function App() {
  const [design, setDesign] = useState<Design | null>(null), [selected, setSelected] = useState(3), [undo, setUndo] = useState<Design[]>([]), [redo, setRedo] = useState<Design[]>([]), [drag, setDrag] = useState<Drag>(null), [status, setStatus] = useState('Loading V5 design…'), [camera, setCamera] = useState<CameraMode>('iso'), [grid, setGrid] = useState(1), [notice, setNotice] = useState<ExportNotice | null>(null);
  useEffect(() => { api<Design>('/api/design').then((loaded) => { setDesign(loaded); setStatus('V5 canonical contour stack loaded.'); }).catch((error: Error) => setStatus(error.message)); }, []);
  useEffect(() => { if (!design) return; const timer = window.setTimeout(() => api<{valid:boolean}>('/api/design/validate', design).then(() => setStatus('Valid canonical contour stack.')).catch((error: Error) => setStatus(`Needs correction: ${error.message}`)), 220); return () => clearTimeout(timer); }, [design]);
  if (!design) return <main className="loading">{status}</main>;
  const update = (fn: (copy: Design) => void) => setDesign((current) => { const next = clone(current!); fn(next); return next; });
  const commit = (before: Design) => { setUndo((history) => [...history.slice(-49), before]); setRedo([]); };
  const undoEdit = () => setUndo((history) => { const previous = history.at(-1); if (!previous) return history; setRedo((future) => [clone(design), ...future]); setDesign(previous); return history.slice(0,-1); });
  const redoEdit = () => setRedo((future) => { const next = future[0]; if (!next) return future; setUndo((history) => [...history, clone(design)]); setDesign(next); return future.slice(1); });
  const persist = async (exporting = false) => {
    if (!exporting) {
      try {
        await api('/api/design/save', design);
        setStatus('Saved designs/current.json.');
      } catch (error) {
        setStatus((error as Error).message);
      }
      return;
    }
    try {
      const result = await api<ExportResult>('/api/design/export', design);
      const files = [result.stl, result.step, ...result.views, ...(result.textured_stl ? [result.textured_stl] : [])];
      setStatus(`Exported ${result.stl} and ${result.step}.`);
      setNotice({ kind: 'success', code: 'EXPORT_COMPLETE', message: 'STL and STEP passed export round-trip validation.', files });
    } catch (unknown) {
      const error = unknown as Error & { code?: string };
      const code = error.code || 'EXPORT_UNEXPECTED';
      setStatus(`Export failed: ${code}.`);
      setNotice({ kind: 'failure', code, message: error.message || 'The export request failed before files could be verified.' });
    }
  };
  return <main>
    <header className="app-header"><div><strong>GECKO HIDE DESIGNER</strong><span>V5 · Rock Shelter</span></div><nav><button onClick={undoEdit} disabled={!undo.length}>Undo</button><button onClick={redoEdit} disabled={!redo.length}>Redo</button><button onClick={() => setCamera('top')}>Top</button><button onClick={() => setCamera('front')}>Front</button><button onClick={() => setCamera('side')}>Side</button><button onClick={() => setCamera('iso')}>Iso</button><button onClick={() => setStatus('Views fitted to all contour levels.')}>Fit</button></nav><div className="snap">Snap <select value={grid} onChange={(event) => setGrid(Number(event.target.value))}><option value={0}>Off</option><option value={1}>1 mm</option><option value={2}>2 mm</option><option value={5}>5 mm</option></select></div></header>
    <div className="workspace"><TopView design={design} selected={selected} drag={drag} setDrag={setDrag} update={update} commit={commit} grid={grid}/><section className="panel preview"><header><strong>3D VIEW</strong><span>Interactive contour preview</span></header><Preview design={design} selected={selected} camera={camera}/></section><EnvelopeView design={design} selected={selected} axis={0} drag={drag} setDrag={setDrag} update={update} commit={commit} grid={grid}/><EnvelopeView design={design} selected={selected} axis={1} drag={drag} setDrag={setDrag} update={update} commit={commit} grid={grid}/></div>
    <section className="lower"><div className="timeline"><strong>CONTOUR LEVELS</strong>{[...design.levels].map((level,index) => <button key={index} className={index===selected?'active':''} onClick={() => setSelected(index)}><span>{level.z.toFixed(0)} mm</span><span>{level.role.replace('_',' ')}</span><span>{level.z_locked?'Z locked':''}</span></button>)}</div><Inspector design={design} selected={selected} update={update} commit={commit}/><aside className="export"><strong>EXPORT</strong><button onClick={() => persist(false)}>Save Design</button><button className="primary" onClick={() => persist(true)}>Generate STL + STEP</button><small>Every generated STL and STEP is re-imported and validated before success is shown.</small></aside></section>
    <footer>{status}</footer>
    {notice && <ExportDialog notice={notice} close={() => setNotice(null)}/>}
  </main>;
}

function Inspector({ design, selected, update, commit }: { design: Design; selected: number; update: (fn: (copy: Design) => void) => void; commit: (before: Design) => void }) {
  const level = design.levels[selected];
  const applyChange = (event: React.ChangeEvent<HTMLInputElement>, apply: (copy: Design, value: number) => void) => update((copy) => apply(copy, Number(event.target.value)));
  const number = (label: string, value: number, apply: (copy: Design, value: number) => void) => <label>{label}<input type="number" value={Number(value.toFixed(2))} onFocus={() => commit(clone(design))} onChange={(event) => applyChange(event, apply)}/></label>;
  return <aside className="inspector">
    <strong>PROPERTIES</strong>
    <fieldset><legend>Shape</legend>
      {number('Height', design.height, (copy, value) => { const ratio = value / copy.height; copy.height = value; copy.levels.forEach((item) => { item.z *= ratio; }); })}
      {number('Wall', design.wall_thickness, (copy, value) => { copy.wall_thickness = value; })}
      {number('Roof', design.roof_thickness, (copy, value) => { copy.roof_thickness = value; })}
      {number('Base plate', design.base_thickness, (copy, value) => { copy.base_thickness = value; })}
    </fieldset>
    <fieldset><legend>Contour level</legend>
      {number('Z', level.z, (copy, value) => moveLevelZ(copy, selected, value))}
      <label>Role<select value={level.role} onFocus={() => commit(clone(design))} onChange={(event) => update((copy) => { copy.levels[selected].role = event.target.value as typeof level.role; })}><option value="wall">wall</option><option value="roof_shoulder">roof shoulder</option><option value="roof_top">roof top</option></select></label>
      <label>Advanced transition<select value={level.surface_mode} onChange={(event) => update((copy) => { copy.levels[selected].surface_mode = event.target.value as typeof level.surface_mode; })}><option value="smooth">smooth</option><option value="ledge">ledge</option></select></label>
    </fieldset>
    <fieldset><legend>Roof</legend>{number('Max overhang', design.max_overhang_xy, (copy, value) => { copy.max_overhang_xy = value; })}{number('Overhang ratio', design.max_overhang_ratio, (copy, value) => { copy.max_overhang_ratio = value; })}</fieldset>
    <fieldset><legend>Surface</legend><label><input type="checkbox" checked={design.appearance.relief_enabled} onChange={(event) => update((copy) => { copy.appearance.relief_enabled = event.target.checked; })}/> Enable shallow relief</label>{number('Depth', design.appearance.relief_depth, (copy, value) => { copy.appearance.relief_depth = value; })}{number('Gap', design.appearance.relief_gap, (copy, value) => { copy.appearance.relief_gap = value; })}</fieldset>
  </aside>;
}

window.addEventListener('keydown',(event)=>{ if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase()==='z') event.preventDefault(); });

import { createRoot } from 'react-dom/client';
createRoot(document.getElementById('root')!).render(<App/>);
