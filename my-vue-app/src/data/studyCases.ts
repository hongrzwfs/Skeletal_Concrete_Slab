export type ParameterKey = 'A' | 'B' | 'C' | 'D'

export interface ParameterSet {
  A: string
  B: string
  C: string
  D: string
}

export interface DiagramAssets {
  forceDiagram: string
  formDiagram: string
  form: string
  stressContour: string
}

export interface MetricItem {
  label: string
  value: string
  unit?: string
}

export interface ResultTableRow {
  item: string
  value: string
  unit: string
  note: string
}

export interface ResultMetrics {
  summary: MetricItem[]
  table: ResultTableRow[]
}

export interface StudyCase {
  id: string
  parameters: ParameterSet
  rationale: string
  diagrams: DiagramAssets
  metrics: ResultMetrics
}

const diagramSet = {
  forceDiagram: '/sample-diagrams/force-diagram.svg',
  formDiagram: '/sample-diagrams/form-diagram.svg',
  form: '/sample-diagrams/spatial-form.svg',
  stressContour: '/sample-diagrams/stress-contour.svg',
}

export const studyCases: StudyCase[] = [
  {
    id: 'FF-001',
    parameters: { A: 'A1', B: 'B1', C: 'C1', D: 'D1' },
    rationale:
      'Baseline reciprocal layout with moderate boundary restraint and balanced tributary loading.',
    diagrams: diagramSet,
    metrics: {
      summary: [
        { label: 'Peak stress', value: '18.6', unit: 'MPa' },
        { label: 'Mean displacement', value: '6.2', unit: 'mm' },
        { label: 'Shape residual', value: '1.8', unit: '%' },
      ],
      table: [
        { item: 'Maximum principal stress', value: '18.6', unit: 'MPa', note: 'Below target threshold' },
        { item: 'Vertical displacement at mid-span', value: '8.4', unit: 'mm', note: 'Reference service state' },
        { item: 'Compression force range', value: '42-96', unit: 'kN', note: 'Balanced force network' },
        { item: 'Iteration count', value: '36', unit: '-', note: 'Converged without damping' },
      ],
    },
  },
  {
    id: 'FF-014',
    parameters: { A: 'A1', B: 'B2', C: 'C1', D: 'D2' },
    rationale:
      'Increased edge restraint and revised load eccentricity to test the sensitivity of the compression field.',
    diagrams: diagramSet,
    metrics: {
      summary: [
        { label: 'Peak stress', value: '21.3', unit: 'MPa' },
        { label: 'Mean displacement', value: '5.7', unit: 'mm' },
        { label: 'Shape residual', value: '2.1', unit: '%' },
      ],
      table: [
        { item: 'Maximum principal stress', value: '21.3', unit: 'MPa', note: 'Stress concentration near support line' },
        { item: 'Vertical displacement at mid-span', value: '7.6', unit: 'mm', note: 'Reduced by boundary stiffness' },
        { item: 'Compression force range', value: '51-118', unit: 'kN', note: 'Higher edge reactions' },
        { item: 'Iteration count', value: '42', unit: '-', note: 'Stable convergence' },
      ],
    },
  },
  {
    id: 'FF-027',
    parameters: { A: 'A2', B: 'B1', C: 'C2', D: 'D1' },
    rationale:
      'Alternative grid proportion with redistributed form-finding target forces for a flatter floor profile.',
    diagrams: diagramSet,
    metrics: {
      summary: [
        { label: 'Peak stress', value: '16.9', unit: 'MPa' },
        { label: 'Mean displacement', value: '7.1', unit: 'mm' },
        { label: 'Shape residual', value: '1.5', unit: '%' },
      ],
      table: [
        { item: 'Maximum principal stress', value: '16.9', unit: 'MPa', note: 'Most uniform sample case' },
        { item: 'Vertical displacement at mid-span', value: '9.2', unit: 'mm', note: 'Slightly higher deformation' },
        { item: 'Compression force range', value: '39-84', unit: 'kN', note: 'Lower resultant force envelope' },
        { item: 'Iteration count', value: '31', unit: '-', note: 'Fastest sample convergence' },
      ],
    },
  },
  {
    id: 'FF-039',
    parameters: { A: 'A2', B: 'B2', C: 'C2', D: 'D2' },
    rationale:
      'High-restraint comparative case used to inspect stress migration after the final form transfer.',
    diagrams: diagramSet,
    metrics: {
      summary: [
        { label: 'Peak stress', value: '24.8', unit: 'MPa' },
        { label: 'Mean displacement', value: '4.9', unit: 'mm' },
        { label: 'Shape residual', value: '2.6', unit: '%' },
      ],
      table: [
        { item: 'Maximum principal stress', value: '24.8', unit: 'MPa', note: 'Highest sample stress response' },
        { item: 'Vertical displacement at mid-span', value: '6.1', unit: 'mm', note: 'Lowest sample displacement' },
        { item: 'Compression force range', value: '63-136', unit: 'kN', note: 'Dominant support reactions' },
        { item: 'Iteration count', value: '47', unit: '-', note: 'Requires additional relaxation steps' },
      ],
    },
  },
]
