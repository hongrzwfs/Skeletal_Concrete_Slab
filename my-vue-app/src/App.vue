<script setup lang="ts">
import { computed, reactive } from 'vue'
import { studyCases, type ParameterKey, type ParameterSet } from './data/studyCases'

const parameterKeys: ParameterKey[] = ['A', 'B', 'C', 'D']

const stageLabels = [
  { key: 'forceDiagram', label: 'Force Diagram' },
  { key: 'formDiagram', label: 'Form Diagram' },
  { key: 'form', label: 'Form' },
  { key: 'stressContour', label: 'Abaqus Stress Contour' },
] as const

const parameterDescriptions: Record<ParameterKey, string> = {
  A: 'Topology family',
  B: 'Boundary restraint',
  C: 'Target force level',
  D: 'Load eccentricity',
}

const parameterOptions = computed(() =>
  parameterKeys.reduce(
    (options, key) => {
      options[key] = [...new Set(studyCases.map((studyCase) => studyCase.parameters[key]))].sort()
      return options
    },
    {} as Record<ParameterKey, string[]>,
  ),
)

const selectedParameters = reactive<ParameterSet>({
  A: studyCases[0].parameters.A,
  B: studyCases[0].parameters.B,
  C: studyCases[0].parameters.C,
  D: studyCases[0].parameters.D,
})

const activeCase = computed(() =>
  studyCases.find((studyCase) =>
    parameterKeys.every((key) => studyCase.parameters[key] === selectedParameters[key]),
  ),
)

const availableCaseCount = computed(() => studyCases.length)

const selectedParameterLabel = computed(() =>
  parameterKeys.map((key) => `${key}=${selectedParameters[key]}`).join(', '),
)
</script>

<template>
  <main class="app-shell">
    <header class="paper-header">
      <div>
        <p class="eyebrow">Reviewer auxiliary website</p>
        <h1>Form-Finding Evidence Chain for a Building Floor Structure</h1>
        <p class="abstract">
          This dashboard links each parameter combination to its corresponding force diagram,
          reciprocal form diagram, generated spatial form, Abaqus stress contour, and numerical
          verification table. It is intended to support transparent review of the form-finding
          reasoning sequence.
        </p>
      </div>

      <dl class="study-meta" aria-label="Study metadata">
        <div>
          <dt>Study type</dt>
          <dd>Architectural engineering form finding</dd>
        </div>
        <div>
          <dt>Visible cases</dt>
          <dd>{{ availableCaseCount }} sample mappings</dd>
        </div>
        <div>
          <dt>Data source</dt>
          <dd>Typed local manifest</dd>
        </div>
      </dl>
    </header>

    <section class="parameter-panel" aria-labelledby="parameter-title">
      <div>
        <p class="section-kicker">Parameter combination</p>
        <h2 id="parameter-title">Select A, B, C, and D</h2>
      </div>

      <div class="parameter-grid">
        <label v-for="key in parameterKeys" :key="key" class="parameter-field">
          <span>
            <strong>{{ key }}</strong>
            {{ parameterDescriptions[key] }}
          </span>
          <select v-model="selectedParameters[key]" :aria-label="`${key} parameter`">
            <option v-for="option in parameterOptions[key]" :key="option" :value="option">
              {{ option }}
            </option>
          </select>
        </label>
      </div>
    </section>

    <section class="case-status" :class="{ unavailable: !activeCase }" aria-live="polite">
      <div>
        <p class="section-kicker">Active mapping</p>
        <h2>{{ activeCase?.id ?? 'Case not available' }}</h2>
        <p>
          {{
            activeCase?.rationale ??
            'The selected parameter combination is not present in the current sample manifest. Add a matching record to connect this combination with diagrams and table data.'
          }}
        </p>
      </div>
      <p class="parameter-token">{{ selectedParameterLabel }}</p>
    </section>

    <template v-if="activeCase">
      <section class="metric-strip" aria-label="Key result metrics">
        <article v-for="metric in activeCase.metrics.summary" :key="metric.label">
          <span>{{ metric.label }}</span>
          <strong>{{ metric.value }}</strong>
          <small>{{ metric.unit }}</small>
        </article>
      </section>

      <section class="stage-section" aria-labelledby="stage-title">
        <div class="section-heading">
          <p class="section-kicker">Reasoning sequence</p>
          <h2 id="stage-title">Linked diagrams and simulation output</h2>
        </div>

        <div class="stage-grid">
          <article v-for="stage in stageLabels" :key="stage.key" class="stage-card">
            <div class="stage-image-frame">
              <img
                :src="activeCase.diagrams[stage.key]"
                :alt="`${stage.label} for ${activeCase.id}`"
              />
              <span>{{ activeCase.id }}</span>
            </div>
            <h3>{{ stage.label }}</h3>
          </article>
        </div>
      </section>

      <section class="table-section" aria-labelledby="table-title">
        <div class="section-heading">
          <p class="section-kicker">Numerical verification</p>
          <h2 id="table-title">Case result table</h2>
        </div>

        <div class="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Item</th>
                <th>Value</th>
                <th>Unit</th>
                <th>Interpretation</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="row in activeCase.metrics.table" :key="row.item">
                <td>{{ row.item }}</td>
                <td>{{ row.value }}</td>
                <td>{{ row.unit }}</td>
                <td>{{ row.note }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>
    </template>
  </main>
</template>
