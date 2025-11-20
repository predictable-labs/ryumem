'use client';

import { useState, useEffect } from 'react';
import { api, ConfigValue } from '@/lib/api';

type Category = 'api_keys' | 'llm' | 'embedding' | 'entity_extraction' | 'search' | 'tool_tracking' | 'community';

interface SettingsState {
  [key: string]: any;
}

interface ChangedFields {
  [key: string]: boolean;
}

export default function SettingsPage() {
  const [activeTab, setActiveTab] = useState<Category>('api_keys');
  const [settings, setSettings] = useState<Record<string, ConfigValue[]>>({});
  const [originalSettings, setOriginalSettings] = useState<SettingsState>({}); // Track original values
  const [localSettings, setLocalSettings] = useState<SettingsState>({});
  const [changedFields, setChangedFields] = useState<ChangedFields>({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<{ type: 'success' | 'error', text: string } | null>(null);

  useEffect(() => {
    loadSettings();
  }, []);

  const loadSettings = async () => {
    try {
      setLoading(true);
      const response = await api.getSettings(false); // Don't mask for editing
      setSettings(response.settings);

      // Initialize local state and original state
      const initial: SettingsState = {};
      Object.values(response.settings).flat().forEach(cfg => {
        initial[cfg.key] = cfg.value;
      });
      setLocalSettings(initial);
      setOriginalSettings(initial); // Store original for comparison
      setChangedFields({}); // Clear changed fields on load
    } catch (error) {
      console.error('Failed to load settings:', error);
      setMessage({ type: 'error', text: 'Failed to load settings' });
    } finally {
      setLoading(false);
    }
  };

  const handleChange = (key: string, value: any) => {
    setLocalSettings(prev => ({ ...prev, [key]: value }));

    // Check if value is actually different from original
    // Need to handle type coercion (e.g., "10" vs 10, "true" vs true)
    const originalValue = originalSettings[key];
    const isActuallyChanged = !areValuesEqual(value, originalValue);

    setChangedFields(prev => {
      const newChangedFields = { ...prev };
      if (isActuallyChanged) {
        newChangedFields[key] = true;
      } else {
        // Remove from changed fields if value matches original
        delete newChangedFields[key];
      }
      return newChangedFields;
    });
  };

  // Helper function to compare values accounting for type coercion
  const areValuesEqual = (a: any, b: any): boolean => {
    // Handle null/undefined
    if (a === b) return true;
    if (a == null || b == null) return false;

    // Handle booleans (including string representations)
    if (typeof a === 'boolean' || typeof b === 'boolean') {
      const aBool = a === true || a === 'true';
      const bBool = b === true || b === 'true';
      return aBool === bBool;
    }

    // Handle numbers (including string representations)
    if (typeof a === 'number' || typeof b === 'number') {
      return Number(a) === Number(b);
    }

    // Handle strings
    return String(a) === String(b);
  };

  const handleSave = async () => {
    try {
      setSaving(true);

      // Get only changed values
      const updates: Record<string, any> = {};
      Object.keys(changedFields).forEach(key => {
        if (changedFields[key]) {
          updates[key] = localSettings[key];
        }
      });

      // Handle provider-specific field cleanup
      // If LLM provider is not Ollama, set Ollama URL to default (not empty)
      if (updates['llm.provider'] && updates['llm.provider'] !== 'ollama') {
        updates['llm.ollama_base_url'] = 'http://localhost:11434';
      } else if (localSettings['llm.provider'] !== 'ollama' && !updates['llm.ollama_base_url']) {
        // Provider wasn't changed but it's still not Ollama - set to default
        updates['llm.ollama_base_url'] = 'http://localhost:11434';
      }

      // Handle provider-specific field cleanup
      // If LLM provider is not Ollama, set Ollama URL to default (not empty)
      if (updates['embedding.provider'] && updates['embedding.provider'] !== 'ollama') {
        updates['embedding.ollama_base_url'] = 'http://localhost:11434';
      } else if (localSettings['embedding.provider'] !== 'ollama' && !updates['embedding.ollama_base_url']) {
        // Provider wasn't changed but it's still not Ollama - set to default
        updates['embedding.ollama_base_url'] = 'http://localhost:11434';
      }

      if (Object.keys(updates).length === 0) {
        setMessage({ type: 'success', text: 'No changes to save' });
        return;
      }

      const result = await api.updateSettings(updates);
      setMessage({
        type: 'success',
        text: `Successfully updated ${result.success_count} setting(s)`
      });

      // Clear changed fields
      setChangedFields({});

      // Reload to get fresh data
      await loadSettings();

      setTimeout(() => setMessage(null), 3000);
    } catch (error: any) {
      console.log({ error })
      setMessage({ type: 'error', text: error.message || 'Failed to save settings' });
    } finally {
      setSaving(false);
    }
  };

  const renderField = (cfg: ConfigValue) => {
    const value = localSettings[cfg.key] ?? cfg.value;
    const isChanged = changedFields[cfg.key];
    const baseClasses = `mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm ${isChanged ? 'bg-yellow-50 border-yellow-400' : ''}`;

    if (cfg.data_type === 'bool') {
      return (
        <input
          type="checkbox"
          checked={value === true || value === 'true'}
          onChange={(e) => handleChange(cfg.key, e.target.checked)}
          className="h-4 w-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500"
        />
      );
    }

    if (cfg.is_sensitive) {
      return (
        <input
          type="password"
          value={value || ''}
          onChange={(e) => handleChange(cfg.key, e.target.value)}
          className={baseClasses}
          placeholder="Enter API key"
        />
      );
    }

    if (cfg.key.includes('provider') || cfg.key.includes('strategy')) {
      let options: string[] = [];
      if (cfg.key === 'llm.provider') {
        options = ['openai', 'gemini', 'ollama', 'litellm'];
      } else if (cfg.key === 'embedding.provider') {
        options = ['ollama', 'openai', 'gemini', 'litellm'];
      } else if (cfg.key === 'search.default_strategy') {
        options = ['semantic', 'traversal', 'hybrid'];
      }

      if (options.length > 0) {
        return (
          <select
            value={value || ''}
            onChange={(e) => handleChange(cfg.key, e.target.value)}
            className={baseClasses}
          >
            {options.map(opt => (
              <option key={opt} value={opt}>{opt}</option>
            ))}
          </select>
        );
      }
    }

    if (cfg.data_type === 'int' || cfg.data_type === 'float') {
      return (
        <input
          type="number"
          value={value ?? ''}
          onChange={(e) => handleChange(cfg.key, cfg.data_type === 'int' ? parseInt(e.target.value) : parseFloat(e.target.value))}
          className={baseClasses}
          step={cfg.data_type === 'float' ? '0.1' : '1'}
        />
      );
    }

    return (
      <input
        type="text"
        value={value || ''}
        onChange={(e) => handleChange(cfg.key, e.target.value)}
        className={baseClasses}
      />
    );
  };

  const tabs: Array<{ id: Category, label: string }> = [
    { id: 'api_keys', label: 'API Keys' },
    { id: 'llm', label: 'LLM' },
    { id: 'embedding', label: 'Embedding' },
    { id: 'search', label: 'Search' },
    { id: 'entity_extraction', label: 'Entity Extraction' },
    { id: 'tool_tracking', label: 'Tool Tracking' },
    { id: 'community', label: 'Community' },
  ];

  const hasChanges = Object.keys(changedFields).length > 0;

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-lg">Loading settings...</div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50 py-8 px-4 sm:px-6 lg:px-8">
      <div className="max-w-6xl mx-auto">
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-gray-900">System Settings</h1>
          <p className="mt-2 text-sm text-gray-600">
            Configure Ryumem system settings. Changes are applied immediately after saving.
          </p>
        </div>

        {message && (
          <div className={`mb-6 p-4 rounded-md ${message.type === 'success' ? 'bg-green-50 text-green-800' : 'bg-red-50 text-red-800'}`}>
            {message.text}
          </div>
        )}

        {hasChanges && (
          <div className="mb-6 p-4 bg-yellow-50 border border-yellow-200 rounded-md flex items-center justify-between">
            <span className="text-yellow-800">You have unsaved changes</span>
            <button
              onClick={handleSave}
              disabled={saving}
              className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50"
            >
              {saving ? 'Saving...' : 'Save Changes'}
            </button>
          </div>
        )}

        {/* Tabs */}
        <div className="border-b border-gray-200 mb-6">
          <nav className="-mb-px flex space-x-8 overflow-x-auto">
            {tabs.map(tab => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`whitespace-nowrap py-4 px-1 border-b-2 font-medium text-sm ${activeTab === tab.id
                  ? 'border-blue-500 text-blue-600'
                  : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                  }`}
              >
                {tab.label}
                {settings[tab.id]?.some(cfg => changedFields[cfg.key]) && (
                  <span className="ml-2 inline-block w-2 h-2 bg-yellow-400 rounded-full"></span>
                )}
              </button>
            ))}
          </nav>
        </div>

        {/* Settings Form */}
        <div className="bg-white shadow rounded-lg p-6">
          {settings[activeTab] ? (
            <div className="space-y-6">
              {settings[activeTab].map(cfg => {
                // Conditional rendering: Hide Ollama URL if provider is not Ollama
                if (cfg.key === 'llm.ollama_base_url' && localSettings['llm.provider'] !== 'ollama') {
                  return null;
                }

                if (cfg.key === 'embedding.ollama_base_url' && localSettings['embedding.provider'] !== 'ollama') {
                  return null;
                }

                return (
                  <div key={cfg.key}>
                    <label className="block text-sm font-medium text-gray-700">
                      {cfg.key.split('.').pop()?.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())}
                      {changedFields[cfg.key] && (
                        <span className="ml-2 text-xs text-yellow-600">(modified)</span>
                      )}
                    </label>
                    <p className="text-xs text-gray-500 mt-1">{cfg.description}</p>
                    <div className="mt-2">
                      {renderField(cfg)}
                    </div>
                  </div>
                );
              })}
            </div>
          ) : (
            <div className="text-center text-gray-500 py-8">
              No settings available for this category
            </div>
          )}
        </div>

        {/* Action Buttons */}
        <div className="mt-6 flex justify-between">
          <button
            onClick={() => {
              if (confirm('Are you sure you want to reset all settings to defaults? This cannot be undone.')) {
                api.resetSettingsToDefaults().then(() => {
                  setMessage({ type: 'success', text: 'Settings reset to defaults' });
                  loadSettings();
                });
              }
            }}
            className="px-4 py-2 border border-gray-300 rounded-md text-gray-700 hover:bg-gray-50"
          >
            Reset to Defaults
          </button>

          <button
            onClick={handleSave}
            disabled={!hasChanges || saving}
            className="px-6 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {saving ? 'Saving...' : 'Save All Changes'}
          </button>
        </div>
      </div>
    </div>
  );
}
