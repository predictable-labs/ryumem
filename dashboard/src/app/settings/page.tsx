'use client';

import { useState, useEffect } from 'react';
import { api, ConfigValue } from '@/lib/api';
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Check, AlertCircle, Save, RotateCcw } from "lucide-react";

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
  const [originalSettings, setOriginalSettings] = useState<SettingsState>({});
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
      const response = await api.getSettings(false);
      setSettings(response.settings);

      const initial: SettingsState = {};
      Object.values(response.settings).flat().forEach(cfg => {
        initial[cfg.key] = cfg.value;
      });
      setLocalSettings(initial);
      setOriginalSettings(initial);
      setChangedFields({});
    } catch (error) {
      console.error('Failed to load settings:', error);
      setMessage({ type: 'error', text: 'Failed to load settings' });
    } finally {
      setLoading(false);
    }
  };

  const handleChange = (key: string, value: any) => {
    setLocalSettings(prev => ({ ...prev, [key]: value }));

    const originalValue = originalSettings[key];
    const isActuallyChanged = !areValuesEqual(value, originalValue);

    setChangedFields(prev => {
      const newChangedFields = { ...prev };
      if (isActuallyChanged) {
        newChangedFields[key] = true;
      } else {
        delete newChangedFields[key];
      }
      return newChangedFields;
    });
  };

  const areValuesEqual = (a: any, b: any): boolean => {
    if (a === b) return true;
    if (a == null || b == null) return false;

    if (typeof a === 'boolean' || typeof b === 'boolean') {
      const aBool = a === true || a === 'true';
      const bBool = b === true || b === 'true';
      return aBool === bBool;
    }

    if (typeof a === 'number' || typeof b === 'number') {
      return Number(a) === Number(b);
    }

    return String(a) === String(b);
  };

  const handleSave = async () => {
    try {
      setSaving(true);

      const updates: Record<string, any> = {};
      Object.keys(changedFields).forEach(key => {
        if (changedFields[key]) {
          updates[key] = localSettings[key];
        }
      });

      if (updates['llm.provider'] && updates['llm.provider'] !== 'ollama') {
        updates['llm.ollama_base_url'] = 'http://100.108.18.43:11434';
      } else if (localSettings['llm.provider'] !== 'ollama' && !updates['llm.ollama_base_url']) {
        updates['llm.ollama_base_url'] = 'http://100.108.18.43:11434';
      }

      if (updates['embedding.provider'] && updates['embedding.provider'] !== 'ollama') {
        updates['embedding.ollama_base_url'] = 'http://100.108.18.43:11434';
      } else if (localSettings['embedding.provider'] !== 'ollama' && !updates['embedding.ollama_base_url']) {
        updates['embedding.ollama_base_url'] = 'http://100.108.18.43:11434';
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

      setChangedFields({});
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

    if (cfg.data_type === 'bool') {
      return (
        <div className="flex items-center space-x-2">
          <input
            type="checkbox"
            id={cfg.key}
            checked={value === true || value === 'true'}
            onChange={(e) => handleChange(cfg.key, e.target.checked)}
            className="h-4 w-4 rounded border-input bg-background text-primary focus:ring-ring"
          />
          <Label htmlFor={cfg.key} className="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70">
            {value ? 'Enabled' : 'Disabled'}
          </Label>
        </div>
      );
    }

    if (cfg.is_sensitive) {
      return (
        <Input
          type="password"
          value={value || ''}
          onChange={(e) => handleChange(cfg.key, e.target.value)}
          className={isChanged ? 'border-yellow-500 bg-yellow-500/10' : ''}
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
          <Select
            value={value || ''}
            onValueChange={(val) => handleChange(cfg.key, val)}
          >
            <SelectTrigger className={isChanged ? 'border-yellow-500 bg-yellow-500/10' : ''}>
              <SelectValue placeholder="Select option" />
            </SelectTrigger>
            <SelectContent>
              {options.map(opt => (
                <SelectItem key={opt} value={opt}>{opt}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        );
      }
    }

    if (cfg.data_type === 'int' || cfg.data_type === 'float') {
      return (
        <Input
          type="number"
          value={value ?? ''}
          onChange={(e) => handleChange(cfg.key, cfg.data_type === 'int' ? parseInt(e.target.value) : parseFloat(e.target.value))}
          className={isChanged ? 'border-yellow-500 bg-yellow-500/10' : ''}
          step={cfg.data_type === 'float' ? '0.1' : '1'}
        />
      );
    }

    return (
      <Input
        type="text"
        value={value || ''}
        onChange={(e) => handleChange(cfg.key, e.target.value)}
        className={isChanged ? 'border-yellow-500 bg-yellow-500/10' : ''}
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
        <div className="flex flex-col items-center gap-2">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
          <div className="text-muted-foreground">Loading settings...</div>
        </div>
      </div>
    );
  }

  return (
    <div className="container mx-auto p-6 max-w-6xl">
      <div className="mb-8 flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">System Settings</h1>
          <p className="mt-2 text-muted-foreground">
            Configure Ryumem system settings. Changes are applied immediately after saving.
          </p>
        </div>
        <div className="flex gap-2">
          <Button
            variant="outline"
            onClick={() => {
              if (confirm('Are you sure you want to reset all settings to defaults? This cannot be undone.')) {
                api.resetSettingsToDefaults().then(() => {
                  setMessage({ type: 'success', text: 'Settings reset to defaults' });
                  loadSettings();
                });
              }
            }}
          >
            <RotateCcw className="mr-2 h-4 w-4" />
            Reset Defaults
          </Button>
          <Button
            onClick={handleSave}
            disabled={!hasChanges || saving}
          >
            {saving ? (
              <>Saving...</>
            ) : (
              <>
                <Save className="mr-2 h-4 w-4" />
                Save Changes
              </>
            )}
          </Button>
        </div>
      </div>

      {message && (
        <Alert className={`mb-6 ${message.type === 'success' ? 'border-green-500/50 text-green-600 dark:text-green-400' : 'border-destructive/50 text-destructive'}`}>
          {message.type === 'success' ? <Check className="h-4 w-4" /> : <AlertCircle className="h-4 w-4" />}
          <AlertDescription>
            {message.text}
          </AlertDescription>
        </Alert>
      )}

      {hasChanges && (
        <Alert className="mb-6 border-yellow-500/50 bg-yellow-500/10 text-yellow-600 dark:text-yellow-400">
          <AlertCircle className="h-4 w-4" />
          <AlertDescription>
            You have unsaved changes. Don't forget to save them.
          </AlertDescription>
        </Alert>
      )}

      <Card>
        <CardContent className="p-6">
          <Tabs value={activeTab} onValueChange={(val) => setActiveTab(val as Category)} className="space-y-6">
            <TabsList className="w-full justify-start overflow-x-auto h-auto p-1">
              {tabs.map(tab => (
                <TabsTrigger key={tab.id} value={tab.id} className="relative">
                  {tab.label}
                  {settings[tab.id]?.some(cfg => changedFields[cfg.key]) && (
                    <span className="absolute -top-1 -right-1 h-2 w-2 rounded-full bg-yellow-500" />
                  )}
                </TabsTrigger>
              ))}
            </TabsList>

            {settings[activeTab] ? (
              <div className="space-y-6">
                {settings[activeTab].map(cfg => {
                  if (cfg.key === 'llm.ollama_base_url' && localSettings['llm.provider'] !== 'ollama') return null;
                  if (cfg.key === 'embedding.ollama_base_url' && localSettings['embedding.provider'] !== 'ollama') return null;

                  return (
                    <div key={cfg.key} className="space-y-2">
                      <Label className="flex items-center gap-2">
                        {cfg.key.split('.').pop()?.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())}
                        {changedFields[cfg.key] && (
                          <span className="text-xs text-yellow-600 dark:text-yellow-400 font-normal">(modified)</span>
                        )}
                      </Label>
                      <p className="text-sm text-muted-foreground">{cfg.description}</p>
                      <div>
                        {renderField(cfg)}
                      </div>
                    </div>
                  );
                })}
              </div>
            ) : (
              <div className="text-center text-muted-foreground py-8">
                No settings available for this category
              </div>
            )}
          </Tabs>
        </CardContent>
      </Card>
    </div>
  );
}
