/** The model list behind the switch dropdown, shared by every screen. */

import { defineStore } from 'pinia'

import * as modelsApi from '@/api/models'
import type { ModelOptionsResponse } from '@/types/api'

interface ModelState {
  active: string | null
  provider: string
  available: boolean
  canSwitch: boolean
  options: ModelOptionsResponse['models']
  loading: boolean
  /** Set while an administrator switches, so the dropdown can show progress. */
  switching: boolean
}

export const useModelStore = defineStore('models', {
  state: (): ModelState => ({
    active: null,
    provider: 'none',
    available: false,
    canSwitch: false,
    options: [],
    loading: false,
    switching: false,
  }),

  actions: {
    async load(): Promise<void> {
      this.loading = true
      try {
        const payload = await modelsApi.listModelOptions()
        this.active = payload.active_model
        this.provider = payload.provider
        this.available = payload.available
        this.canSwitch = payload.can_switch
        this.options = payload.models
      } finally {
        this.loading = false
      }
    },

    /** Switch the model the agent uses. Administrators only. */
    async activate(name: string, options: { preload?: boolean } = {}): Promise<void> {
      this.switching = true
      try {
        const payload = await modelsApi.activateModel(name, options)
        this.active = payload.active_model
        this.provider = payload.provider
        this.available = payload.ollama_online
        this.options = payload.models.map((model) => ({
          name: model.name,
          is_active: model.name === payload.active_model,
          loaded: model.loaded,
          parameter_size: model.parameter_size,
          quantization: model.quantization,
          size_label: model.size_label,
        }))
      } finally {
        this.switching = false
      }
    },
  },
})
