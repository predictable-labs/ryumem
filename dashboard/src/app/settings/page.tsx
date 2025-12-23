'use client';

import { useState, useEffect } from 'react';
import { api, ConfigValue, getFullApiKey } from '@/lib/api';
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Check, AlertCircle, Save, RotateCcw, Trash2, AlertTriangle, Copy, Key, Eye, EyeOff } from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";

type Category = 'api_keys' | 'llm' | 'embedding' | 'entity_extraction' | 'episode' | 'search' | 'tool_tracking' | 'agent' | 'system';

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
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [confirmText, setConfirmText] = useState('');
  const [isDeleting, setIsDeleting] = useState(false);
  const [userApiKey, setUserApiKey] = useState<string | null>(null);
  const [githubUsername, setGithubUsername] = useState<string | null>(null);
  const [showApiKey, setShowApiKey] = useState(false);
  const [apiKeyCopied, setApiKeyCopied] = useState(false);

  useEffect(() => {
    loadSettings();
    loadUserApiKey();
  }, []);

  const loadUserApiKey = async () => {
    try {
      const response = await getFullApiKey();
      setUserApiKey(response.api_key);
      setGithubUsername(response.github_username || null);
    } catch (error) {
      console.error('Failed to load API key:', error);
    }
  };

  const copyApiKey = async () => {
    if (userApiKey) {
      await navigator.clipboard.writeText(userApiKey);
      setApiKeyCopied(true);
      setTimeout(() => setApiKeyCopied(false), 2000);
    }
  };

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

  const handleDeleteDatabase = async () => {
    if (confirmText !== 'DELETE') {
      setMessage({ type: 'error', text: 'Please type DELETE to confirm' });
      return;
    }

    try {
      setIsDeleting(true);
      await api.deleteDatabase();
      setMessage({
        type: 'success',
        text: 'Database deleted successfully. All data has been permanently removed.'
      });
      setDeleteDialogOpen(false);
      setConfirmText('');

      // Reload settings after deletion
      setTimeout(() => {
        loadSettings();
      }, 1000);
    } catch (error: any) {
      console.error('Delete database error:', error);
      setMessage({
        type: 'error',
        text: error.message || 'Failed to delete database'
      });
    } finally {
      setIsDeleting(false);
    }
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
        updates['llm.ollama_base_url'] = 'http://localhost:11434';
      } else if (localSettings['llm.provider'] !== 'ollama' && !updates['llm.ollama_base_url']) {
        updates['llm.ollama_base_url'] = 'http://localhost:11434';
      }

      if (updates['embedding.provider'] && updates['embedding.provider'] !== 'ollama') {
        updates['embedding.ollama_base_url'] = 'http://localhost:11434';
      } else if (localSettings['embedding.provider'] !== 'ollama' && !updates['embedding.ollama_base_url']) {
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
    { id: 'episode', label: 'Episode' },
    { id: 'search', label: 'Search' },
    { id: 'entity_extraction', label: 'Entity Extraction' },
    { id: 'tool_tracking', label: 'Tool Tracking' },
    { id: 'agent', label: 'Agent' },
    { id: 'system', label: 'System' },
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
            You have unsaved changes. Don&apos;t forget to save them.
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

      {/* Your API Key Section */}
      {userApiKey && (
        <Card className="mt-8 border-primary/30 bg-primary/5">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Key className="h-5 w-5" />
              Your API Key
            </CardTitle>
            <CardDescription>
              Use this API key in scripts, MCP servers, and other integrations.
              {githubUsername && (
                <span className="ml-1">
                  Connected to GitHub as <strong>@{githubUsername}</strong>
                </span>
              )}
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="flex items-center gap-2">
              <div className="flex-1 relative">
                <Input
                  type={showApiKey ? "text" : "password"}
                  value={userApiKey}
                  readOnly
                  className="pr-20 font-mono text-sm"
                />
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  className="absolute right-1 top-1/2 -translate-y-1/2 h-7 px-2"
                  onClick={() => setShowApiKey(!showApiKey)}
                >
                  {showApiKey ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                </Button>
              </div>
              <Button
                variant="outline"
                size="sm"
                onClick={copyApiKey}
                className="shrink-0"
              >
                {apiKeyCopied ? (
                  <>
                    <Check className="mr-2 h-4 w-4 text-green-500" />
                    Copied!
                  </>
                ) : (
                  <>
                    <Copy className="mr-2 h-4 w-4" />
                    Copy
                  </>
                )}
              </Button>
            </div>
            <p className="mt-3 text-xs text-muted-foreground">
              Keep this key secret. Use it as the <code className="bg-muted px-1 py-0.5 rounded">RYUMEM_API_KEY</code> environment variable.
            </p>
          </CardContent>
        </Card>
      )}

      {/* Danger Zone */}
      <Card className="mt-8 border-red-500/50 bg-red-500/5">
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-red-600 dark:text-red-400">
            <AlertTriangle className="h-5 w-5" />
            Danger Zone
          </CardTitle>
          <CardDescription>
            Irreversible actions that permanently delete data
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex items-start justify-between p-4 border border-red-500/30 rounded-lg">
            <div className="flex-1">
              <h3 className="font-semibold text-red-600 dark:text-red-400 mb-1">
                Delete All Database Data
              </h3>
              <p className="text-sm text-muted-foreground">
                Permanently delete all episodes, entities, relationships, and memories from the database.
                This action cannot be undone. The database file will remain but will be empty.
              </p>
            </div>
            <Dialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
              <DialogTrigger asChild>
                <Button
                  variant="destructive"
                  className="ml-4"
                  onClick={() => setConfirmText('')}
                >
                  <Trash2 className="mr-2 h-4 w-4" />
                  Delete Database
                </Button>
              </DialogTrigger>
              <DialogContent className="sm:max-w-[500px]">
                <DialogHeader>
                  <DialogTitle className="flex items-center gap-2 text-red-600 dark:text-red-400">
                    <AlertTriangle className="h-5 w-5" />
                    Confirm Database Deletion
                  </DialogTitle>
                  <DialogDescription className="pt-4 space-y-4">
                    <Alert className="border-red-500/50 bg-red-500/10">
                      <AlertTriangle className="h-4 w-4 text-red-600 dark:text-red-400" />
                      <AlertDescription className="text-red-600 dark:text-red-400">
                        <strong>Warning:</strong> This action is irreversible!
                      </AlertDescription>
                    </Alert>
                    <div className="space-y-2 text-sm">
                      <p>This will permanently delete:</p>
                      <ul className="list-disc list-inside space-y-1 ml-2">
                        <li>All episodes and memories</li>
                        <li>All entities and their properties</li>
                        <li>All relationships between entities</li>
                        <li>All metadata and configurations</li>
                      </ul>
                    </div>
                    <div className="space-y-2">
                      <Label htmlFor="confirm-text">
                        Type <strong>DELETE</strong> to confirm:
                      </Label>
                      <Input
                        id="confirm-text"
                        value={confirmText}
                        onChange={(e) => setConfirmText(e.target.value)}
                        placeholder="DELETE"
                        className="font-mono"
                      />
                    </div>
                  </DialogDescription>
                </DialogHeader>
                <DialogFooter>
                  <Button
                    variant="outline"
                    onClick={() => {
                      setDeleteDialogOpen(false);
                      setConfirmText('');
                    }}
                    disabled={isDeleting}
                  >
                    Cancel
                  </Button>
                  <Button
                    variant="destructive"
                    onClick={handleDeleteDatabase}
                    disabled={confirmText !== 'DELETE' || isDeleting}
                  >
                    {isDeleting ? (
                      <>Deleting...</>
                    ) : (
                      <>
                        <Trash2 className="mr-2 h-4 w-4" />
                        Delete All Data
                      </>
                    )}
                  </Button>
                </DialogFooter>
              </DialogContent>
            </Dialog>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
