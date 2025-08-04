// Copyright © Amazon.com and Affiliates: This deliverable is considered Developed Content as defined in the AWS Service
// Terms and the SOW between the parties dated 2025.

'use client';

import { useState, useEffect } from 'react';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '@/components/ui/dialog';
import { Label } from '@/components/ui/label';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { useStore } from '@/lib/store/index';
import { Model } from '@/lib/api/resources/model';
import { useModels } from '@/hooks/use-models';
import {
  useDefaultModel,
  getEffectiveModelId,
} from '@/hooks/use-default-model';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { cn } from '@/lib/utils';
import {
  BookPlus,
  UserPlus,
  UserCircle,
  BookText,
  Plus,
  Pencil,
  Trash2,
  X,
  Shield,
  AlertCircle,
  Settings,
  Monitor,
  Sun,
  Moon,
  Search,
} from 'lucide-react';
import { useTheme } from 'next-themes';
import { ToggleGroup, ToggleGroupItem } from '@/components/ui/toggle-group';
import { GuardrailsPanel } from '@/components/settings/guardrail';
import { AdminGuard } from '@/components/auth/admin-guard';
import { api } from '@/lib/api/index';
import {
  Persona,
  Prompt,
  CreatePersonaRequest,
  UpdatePersonaRequest,
  CreatePromptRequest,
  UpdatePromptRequest,
  GuardrailInfo,
  GuardrailDetail,
  GuardrailCreate,
  GuardrailUpdate,
  GuardrailContentFilter,
  GuardrailPiiEntity,
  GuardrailWordFilter,
  GuardrailDeniedTopic,
  ContentFilterType,
  FilterStrength,
  PiiEntityType,
  PiiAction,
} from '@/lib/types';
import { Textarea } from '@/components/ui/textarea';
import { Badge } from '@/components/ui/badge';
import { ScrollArea } from '@/components/ui/scroll-area';
import { PersonaSelector } from '@/components/chat/input/persona-selector';
import { Separator } from '@/components/ui/separator';
import {
  usePersonas,
  useCreatePersona,
  useUpdatePersona,
  useDeletePersona,
} from '@/hooks/use-personas';
import {
  usePrompts,
  useCreatePrompt,
  useUpdatePrompt,
  useDeletePrompt,
} from '@/hooks/use-prompts';

interface SettingsDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

// Personas Panel Component
function PersonasPanel() {
  // React Query hooks
  const { data: personas = [], isLoading, error: queryError } = usePersonas();
  const createPersonaMutation = useCreatePersona();
  const updatePersonaMutation = useUpdatePersona();
  const deletePersonaMutation = useDeletePersona();

  // Local state
  const [error, setError] = useState<string | null>(null);
  const [isEditing, setIsEditing] = useState(false);
  const [editingPersona, setEditingPersona] = useState<Persona | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [formData, setFormData] = useState<CreatePersonaRequest>({
    name: '',
    description: '',
    prompt: '',
  });

  // Filter personas based on search query
  const filteredPersonas = personas.filter(
    (persona) =>
      searchQuery === '' ||
      persona.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      persona.description.toLowerCase().includes(searchQuery.toLowerCase()),
  );

  // Set error message from query if available
  useEffect(() => {
    if (queryError) {
      setError('Failed to load personas. Please try again.');
    } else {
      setError(null);
    }
  }, [queryError]);

  // Handle form input changes
  const handleInputChange = (
    e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>,
  ) => {
    const { name, value } = e.target;
    setFormData((prev) => ({ ...prev, [name]: value }));
  };

  // Start editing a persona
  const handleEdit = (persona: Persona) => {
    setEditingPersona(persona);
    setFormData({
      name: persona.name,
      description: persona.description,
      prompt: persona.prompt,
    });
    setIsEditing(true);
  };

  // Start creating a new persona
  const handleCreate = () => {
    setEditingPersona(null);
    setFormData({
      name: '',
      description: '',
      prompt: '',
    });
    setIsEditing(true);
  };

  // Save persona (create or update)
  const handleSave = async () => {
    try {
      setError(null);
      if (editingPersona) {
        // Update existing persona
        await updatePersonaMutation.mutateAsync({
          personaId: editingPersona.persona_id,
          request: formData as UpdatePersonaRequest,
        });
      } else {
        // Create new persona
        await createPersonaMutation.mutateAsync(formData);
      }
      setIsEditing(false);
    } catch (error) {
      console.error('Failed to save persona:', error);
      setError('Failed to save persona. Please try again.');
    }
  };

  // Delete a persona
  const handleDelete = async (personaId: string) => {
    if (!confirm('Are you sure you want to delete this persona?')) return;

    try {
      setError(null);
      await deletePersonaMutation.mutateAsync(personaId);
    } catch (error) {
      console.error('Failed to delete persona:', error);
      setError('Failed to delete persona. Please try again.');
    }
  };

  // Cancel editing
  const handleCancel = () => {
    setIsEditing(false);
  };

  // Check if any mutation is in progress
  const isMutating =
    createPersonaMutation.isPending ||
    updatePersonaMutation.isPending ||
    deletePersonaMutation.isPending;

  // Render form for creating/editing
  if (isEditing) {
    return (
      <div className="grid gap-4">
        <div className="flex items-center justify-between">
          <h3 className="text-lg font-medium">
            {editingPersona ? 'Edit Persona' : 'Create New Persona'}
          </h3>
        </div>

        <div className="grid gap-3">
          <div>
            <Label htmlFor="name">Name</Label>
            <Input
              id="name"
              name="name"
              value={formData.name}
              onChange={handleInputChange}
              placeholder="Persona name"
              className="mt-1 bg-card"
            />
          </div>

          <div>
            <Label htmlFor="description">Description</Label>
            <Input
              id="description"
              name="description"
              value={formData.description}
              onChange={handleInputChange}
              placeholder="Brief description"
              className="mt-1 bg-card border"
            />
          </div>

          <div>
            <Label htmlFor="prompt">System Prompt</Label>
            <Textarea
              id="prompt"
              name="prompt"
              value={formData.prompt}
              onChange={handleInputChange}
              placeholder="Enter the system prompt for this persona"
              className="mt-1 min-h-[120px] bg-card"
            />
          </div>
        </div>

        {error && <p className="text-sm text-red-500">{error}</p>}

        <div className="flex justify-between gap-2 mt-2">
          <Button
            variant="destructive"
            onClick={() =>
              editingPersona && handleDelete(editingPersona.persona_id)
            }
            disabled={!editingPersona || isMutating}
          >
            <Trash2 className="mr-2 h-4 w-4" />
            Delete
          </Button>
          <div className="flex gap-2">
            <Button variant="outline" onClick={handleCancel}>
              Cancel
            </Button>
            <Button onClick={handleSave} disabled={isMutating}>
              {isMutating ? 'Saving...' : 'Save Persona'}
            </Button>
          </div>
        </div>
      </div>
    );
  }

  // Render list of personas
  return (
    <div className="grid gap-4">
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-medium">Manage Personas</h3>
        <Button onClick={handleCreate} size="sm">
          Create Persona
        </Button>
      </div>

      <p className="text-sm text-muted-foreground">
        Personas allow you to customize how the AI responds by giving it a
        specific role or personality. Create personas with tailored system
        prompts to guide the AI&apos;s behavior in conversations.
      </p>

      <div className="relative">
        <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-muted-foreground" />
        <Input
          placeholder="Search personas..."
          className="pl-10 pr-10"
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
        />
        {searchQuery && (
          <Button
            variant="ghost"
            size="icon"
            className="absolute right-2 top-1/2 transform -translate-y-1/2 h-6 w-6"
            onClick={() => setSearchQuery('')}
          >
            <X className="h-3 w-3" />
          </Button>
        )}
      </div>

      {error && <p className="text-sm text-red-500">{error}</p>}

      {isLoading ? (
        <p className="text-sm text-muted-foreground">Loading personas...</p>
      ) : filteredPersonas.length === 0 ? (
        <p className="text-sm text-muted-foreground"></p>
      ) : (
        <div className="mt-4">
          <ScrollArea className="pr-4 h-[400px]">
            <div className="grid grid-cols-2 gap-3">
              {filteredPersonas.map((persona) => (
                <div
                  key={persona.persona_id}
                  className="border rounded-md p-3 bg-card text-card-foreground cursor-pointer hover:border-primary/50"
                  onClick={() => handleEdit(persona)}
                >
                  <div className="flex items-start justify-between">
                    <div>
                      <h4 className="text-sm">{persona.name}</h4>
                      <p className="text-xs text-muted-foreground">
                        {persona.description}
                      </p>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </ScrollArea>
        </div>
      )}
    </div>
  );
}

// Prompts Panel Component
function PromptsPanel() {
  // State for category filtering
  const [selectedCategory, setSelectedCategory] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState('');

  // React Query hooks
  const {
    data: prompts = [],
    isLoading,
    error: queryError,
  } = usePrompts(100, selectedCategory || undefined);
  const createPromptMutation = useCreatePrompt();
  const updatePromptMutation = useUpdatePrompt();
  const deletePromptMutation = useDeletePrompt();

  // Local state
  const [error, setError] = useState<string | null>(null);
  const [isEditing, setIsEditing] = useState(false);
  const [editingPrompt, setEditingPrompt] = useState<Prompt | null>(null);
  const [formData, setFormData] = useState<CreatePromptRequest>({
    name: '',
    description: '',
    content: '',
    category: '',
    tags: [],
  });

  // Filter prompts based on search query
  const filteredPrompts = prompts.filter(
    (prompt: Prompt) =>
      searchQuery === '' ||
      prompt.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      prompt.description.toLowerCase().includes(searchQuery.toLowerCase()) ||
      prompt.tags.some((tag) =>
        tag.toLowerCase().includes(searchQuery.toLowerCase()),
      ) ||
      prompt.category.toLowerCase().includes(searchQuery.toLowerCase()),
  );

  // Extract unique categories from prompts
  const categories = Array.from(
    new Set(prompts.map((prompt: Prompt) => prompt.category)),
  ).filter(Boolean);

  // Set error message from query if available
  useEffect(() => {
    if (queryError) {
      setError('Failed to load prompts. Please try again.');
    } else {
      setError(null);
    }
  }, [queryError]);

  // Handle form input changes
  const handleInputChange = (
    e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>,
  ) => {
    const { name, value } = e.target;
    setFormData((prev) => ({ ...prev, [name]: value }));
  };

  // Handle tags input (comma-separated)
  const handleTagsChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const tagsString = e.target.value;
    const tagsArray = tagsString
      .split(',')
      .map((tag) => tag.trim())
      .filter(Boolean);
    setFormData((prev) => ({ ...prev, tags: tagsArray }));
  };

  // Start editing a prompt
  const handleEdit = (prompt: Prompt) => {
    setEditingPrompt(prompt);
    setFormData({
      name: prompt.name,
      description: prompt.description,
      content: prompt.content,
      category: prompt.category,
      tags: prompt.tags,
    });
    setIsEditing(true);
  };

  // Start creating a new prompt
  const handleCreate = () => {
    setEditingPrompt(null);
    setFormData({
      name: '',
      description: '',
      content: '',
      category: selectedCategory || '',
      tags: [],
    });
    setIsEditing(true);
  };

  // Save prompt (create or update)
  const handleSave = async () => {
    try {
      setError(null);
      if (editingPrompt) {
        // Update existing prompt
        await updatePromptMutation.mutateAsync({
          promptId: editingPrompt.prompt_id,
          request: formData as UpdatePromptRequest,
        });
      } else {
        // Create new prompt
        await createPromptMutation.mutateAsync(formData);
      }
      setIsEditing(false);
    } catch (error) {
      console.error('Failed to save prompt:', error);
      setError('Failed to save prompt. Please try again.');
    }
  };

  // Delete a prompt
  const handleDelete = async (promptId: string) => {
    if (!confirm('Are you sure you want to delete this prompt?')) return;

    try {
      setError(null);
      await deletePromptMutation.mutateAsync(promptId);
    } catch (error) {
      console.error('Failed to delete prompt:', error);
      setError('Failed to delete prompt. Please try again.');
    }
  };

  // Cancel editing
  const handleCancel = () => {
    setIsEditing(false);
  };

  // Check if any mutation is in progress
  const isMutating =
    createPromptMutation.isPending ||
    updatePromptMutation.isPending ||
    deletePromptMutation.isPending;

  // Render form for creating/editing
  if (isEditing) {
    return (
      <div className="grid gap-4">
        <div className="flex items-center justify-between">
          <h3 className="text-lg font-medium">
            {editingPrompt ? 'Edit Prompt' : 'Create New Prompt'}
          </h3>
        </div>

        <div className="grid gap-3">
          <div>
            <Label htmlFor="name">Name</Label>
            <Input
              id="name"
              name="name"
              value={formData.name}
              onChange={handleInputChange}
              placeholder="Prompt name"
              className="mt-1 bg-card"
            />
          </div>

          <div>
            <Label htmlFor="description">Description</Label>
            <Input
              id="description"
              name="description"
              value={formData.description}
              onChange={handleInputChange}
              placeholder="Brief description"
              className="mt-1 bg-card"
            />
          </div>

          <div>
            <Label htmlFor="category">Category</Label>
            <Input
              id="category"
              name="category"
              value={formData.category}
              onChange={handleInputChange}
              placeholder="Category"
              className="mt-1 bg-card"
            />
          </div>

          <div>
            <Label htmlFor="tags">Tags (comma-separated)</Label>
            <Input
              id="tags"
              name="tags"
              value={formData.tags?.join(', ') || ''}
              onChange={handleTagsChange}
              placeholder="tag1, tag2, tag3"
              className="mt-1 bg-card"
            />
          </div>

          <div>
            <Label htmlFor="content">Prompt Content</Label>
            <Textarea
              id="content"
              name="content"
              value={formData.content}
              onChange={handleInputChange}
              placeholder="Enter the prompt content"
              className="mt-1 min-h-[120px] bg-card"
            />
          </div>
        </div>

        {error && <p className="text-sm text-red-500">{error}</p>}

        <div className="flex justify-between gap-2 mt-6 mb-6">
          <Button
            variant="destructive"
            onClick={() =>
              editingPrompt && handleDelete(editingPrompt.prompt_id)
            }
            disabled={!editingPrompt || isMutating}
          >
            <Trash2 className="mr-2 h-4 w-4" />
            Delete
          </Button>
          <div className="flex gap-2">
            <Button variant="outline" onClick={handleCancel}>
              Cancel
            </Button>
            <Button onClick={handleSave} disabled={isMutating}>
              {isMutating ? 'Saving...' : 'Save Prompt'}
            </Button>
          </div>
        </div>
      </div>
    );
  }

  // Render list of prompts
  return (
    <div className="grid gap-4">
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-medium">Prompt Library</h3>
        <Button onClick={handleCreate} size="sm">
          Create Prompt
          <BookPlus className="ml-2" />
        </Button>
      </div>

      <p className="text-sm text-muted-foreground">
        The Prompt Library lets you save and organize frequently used prompts.
        Create categorized prompts that can be quickly applied to new
        conversations, saving time and ensuring consistency.
      </p>

      <div className="relative py-1">
        <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-muted-foreground" />
        <Input
          placeholder="Search prompts..."
          className="pl-10 pr-10"
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
        />
        {searchQuery && (
          <Button
            variant="ghost"
            size="icon"
            className="absolute right-2 top-1/2 transform -translate-y-1/2 h-6 w-6"
            onClick={() => setSearchQuery('')}
          >
            <X className="h-3 w-3" />
          </Button>
        )}
      </div>

      {/* Category filter */}
      {categories.length > 0 && (
        <div className="flex flex-wrap gap-2 mb-2 mx-1">
          <Badge
            variant={selectedCategory === null ? 'default' : 'outline'}
            className="cursor-pointer"
            onClick={() => setSelectedCategory(null)}
          >
            All
          </Badge>
          {categories.map((category: unknown) => (
            <Badge
              key={String(category)}
              variant={
                selectedCategory === String(category) ? 'default' : 'outline'
              }
              className="cursor-pointer"
              onClick={() => setSelectedCategory(String(category))}
            >
              {String(category)}
            </Badge>
          ))}
        </div>
      )}

      {error && <p className="text-sm text-red-500">{error}</p>}

      {isLoading ? (
        <p className="text-sm text-muted-foreground">Loading prompts...</p>
      ) : filteredPrompts.length === 0 ? (
        <p className="text-sm text-muted-foreground">
          No prompts available. Create one to get started.
        </p>
      ) : (
        <div className="mt-4">
          <ScrollArea className="pr-4 h-[400px]">
            <div className="grid grid-cols-2 gap-3">
              {filteredPrompts.map((prompt: Prompt) => (
                <div
                  key={prompt.prompt_id}
                  className="border rounded-md p-3 bg-card text-card-foreground cursor-pointer hover:border-primary/50"
                  onClick={() => handleEdit(prompt)}
                >
                  <div className="flex items-start justify-between">
                    <div>
                      <h4 className="font-medium">{prompt.name}</h4>
                      <p className="text-sm text-muted-foreground">
                        {prompt.description}
                      </p>
                      <div className="flex flex-wrap gap-1 mt-1">
                        <Badge variant="secondary" className="text-xs">
                          {prompt.category}
                        </Badge>
                        {prompt.tags.map((tag: string) => (
                          <Badge
                            key={tag}
                            variant="outline"
                            className="text-xs"
                          >
                            {tag}
                          </Badge>
                        ))}
                      </div>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </ScrollArea>
        </div>
      )}
    </div>
  );
}

// Preferences Panel Component
function PreferencesPanel() {
  const { selectedModelId, setSelectedModel } = useStore();
  const { theme, setTheme } = useTheme();
  const [personas, setPersonas] = useState<Persona[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [selectedModel, setSelectedModelState] = useState(selectedModelId);

  // Use React Query hook for models
  const {
    data: models = [],
    isLoading: isLoadingModels,
    error: modelQueryError,
  } = useModels();

  // Get default model logic
  const { defaultModel } = useDefaultModel();

  // Track model error state
  const [modelError, setModelError] = useState<string | null>(null);

  // Get effective model ID and check if using default
  const effectiveModelId = getEffectiveModelId(
    selectedModelId || null,
    defaultModel,
  );
  const isUsingDefault = !selectedModelId && defaultModel;

  // Update error state when query error changes
  useEffect(() => {
    if (modelQueryError) {
      setModelError('Failed to load models. Please try again.');
    } else {
      setModelError(null);
    }
  }, [modelQueryError]);

  // Fetch personas from API
  const fetchPersonas = async () => {
    try {
      setError(null);
      const response = await api.getPersonas();
      setPersonas(response.personas);
    } catch (error) {
      console.error('Failed to fetch personas:', error);
      setError('Failed to load personas. Please try again.');
    }
  };

  useEffect(() => {
    fetchPersonas();
  }, []);

  // Autosave functionality
  useEffect(() => {
    // Save model selection when it changes
    if (
      selectedModel &&
      selectedModel !== selectedModelId &&
      setSelectedModel
    ) {
      setSelectedModel(selectedModel);
    }
  }, [selectedModel, selectedModelId, setSelectedModel]);

  // Handle model change
  const handleModelChange = (value: string) => {
    setSelectedModelState(value);
    // Immediately update the global store to ensure the change is reflected everywhere
    if (setSelectedModel) {
      setSelectedModel(value);
    }
  };

  return (
    <div className="grid gap-16">
      {/* Default Persona */}
      <div className="grid gap-2">
        <div className="grid grid-cols-2 gap-8">
          <div className="justify-self-start">
            <h3 className="text-lg font-medium">Default Persona</h3>
            <p className="text-xs text-muted-foreground">
              Choose a persona for the AI to adopt during conversations
            </p>
          </div>
          <div className="justify-self-end w-full">
            <PersonaSelector />
            {personas.length === 0 && (
              <Button
                variant="outline"
                size="sm"
                className="mt-2 w-fit"
                onClick={() => {
                  const personasTab =
                    document.querySelector('[value="personas"]');
                  if (personasTab) {
                    personasTab.dispatchEvent(new MouseEvent('click'));
                  }
                }}
              >
                <Plus className="mr-2 h-4 w-4" />
                Create New Persona
              </Button>
            )}
          </div>
        </div>
      </div>

      {/* Theme Mode */}
      <div className="grid gap-2">
        <div className="grid grid-cols-2 gap-8 w-full">
          <div className="justify-self-start">
            <h3 className="text-lg font-medium">Theme Mode</h3>
            <p className="text-xs text-muted-foreground">
              Choose between light, dark, or system theme
            </p>
          </div>
          <div className="justify-self-end w-full">
            <ToggleGroup
              type="single"
              value={theme}
              onValueChange={(value) => value && setTheme(value)}
              className="justify-between w-full"
            >
              <ToggleGroupItem
                value="light"
                aria-label="Light Mode"
                className="flex items-center gap-1"
              >
                <Sun className="h-4 w-4" />
                Light
              </ToggleGroupItem>
              <ToggleGroupItem
                value="dark"
                aria-label="Dark Mode"
                className="flex items-center gap-1"
              >
                <Moon className="h-4 w-4" />
                Dark
              </ToggleGroupItem>
              <ToggleGroupItem
                value="system"
                aria-label="System Mode"
                className="flex items-center gap-1"
              >
                <Monitor className="h-4 w-4" />
                System
              </ToggleGroupItem>
            </ToggleGroup>
          </div>
        </div>
      </div>

      {/* Default Model */}
      <div className="grid gap-2">
        <div className="grid grid-cols-2 gap-8">
          <div className="justify-self-start">
            <h3 className="text-lg font-medium">Default Model</h3>
            <p className="text-xs text-muted-foreground">
              Set your preferred AI model for new conversations
            </p>
          </div>
          <div className="justify-self-end w-full">
            <Select
              value={selectedModel || undefined}
              onValueChange={handleModelChange}
              disabled={isLoadingModels}
            >
              <SelectTrigger className="w-full bg-card">
                <SelectValue
                  placeholder={
                    isLoadingModels
                      ? 'Loading models...'
                      : 'Select default model'
                  }
                />
              </SelectTrigger>
              <SelectContent>
                {models.map((model: Model) => (
                  <SelectItem key={model.id} value={model.id}>
                    <div className="flex items-center justify-between w-full">
                      <span>
                        {model.provider} {model.name}
                      </span>
                      {model.id === defaultModel?.id && !selectedModelId && (
                        <Badge variant="secondary" className="ml-2 text-xs">
                          Default
                        </Badge>
                      )}
                    </div>
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            {isUsingDefault && (
              <p className="text-xs text-muted-foreground mt-1">
                Currently using {defaultModel?.provider} {defaultModel?.name} as
                the default model
              </p>
            )}
            {modelError && (
              <p className="text-xs text-red-500 mt-1">{modelError}</p>
            )}
          </div>
        </div>
      </div>

      {/* Keyboard Shortcuts */}
      <div className="grid gap-2">
        <div className="grid grid-cols-2 gap-8">
          <div className="justify-self-start">
            <h3 className="text-lg font-medium">Keyboard Shortcuts</h3>
            <p className="text-xs text-muted-foreground">
              Common keyboard shortcuts for the chat interface
            </p>
          </div>
          <div className="justify-self-end w-full">
            <div className="bg-muted/50 rounded-md p-3">
              <div className="grid grid-cols-2 gap-2 text-sm">
                <div>Send message</div>
                <div className="text-right font-mono text-xs bg-muted px-2 py-1 rounded">
                  Enter
                </div>
                <div>New line</div>
                <div className="text-right font-mono text-xs bg-muted px-2 py-1 rounded">
                  Shift + Enter
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export function SettingsDialog({ open, onOpenChange }: SettingsDialogProps) {
  const [activeTab, setActiveTab] = useState('preferences');

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        className={cn(
          'sm:max-w-[900px] sm:w-[90vw] sm:h-[75vh] h-[100vh] p-0 flex flex-col',
        )}
      >
        <DialogHeader className="px-6 pt-6 pb-2">
          <DialogTitle className="text-xl items-center gap-2">
            <span>Settings</span>
          </DialogTitle>
        </DialogHeader>

        <Tabs
          defaultValue="preferences"
          value={activeTab}
          onValueChange={setActiveTab}
          className="flex flex-col sm:flex-row flex-1 overflow-hidden "
        >
          <div className="sm:border-r sm:w-48 sm:flex-shrink-0 w-full border-b sm:border-b-0">
            <TabsList className="bg-transparent sm:flex-col flex-row items-start p-2 gap-1 h-full justify-start overflow-x-auto">
              <TabsTrigger
                value="preferences"
                className="w-full justify-start data-[state=active]:bg-muted data-[state=active]:shadow-none rounded-md px-3 py-2"
              >
                <Settings className="mr-2 h-4 w-4" />
                Preferences
              </TabsTrigger>
              <TabsTrigger
                value="personas"
                className="w-full justify-start data-[state=active]:bg-muted data-[state=active]:shadow-none rounded-md px-3 py-2"
              >
                <UserCircle className="mr-2 h-4 w-4" />
                Personas
              </TabsTrigger>
              <TabsTrigger
                value="prompts"
                className="w-full justify-start data-[state=active]:bg-muted data-[state=active]:shadow-none rounded-md px-3 py-2"
              >
                <BookText className="mr-2 h-4 w-4" />
                Prompts
              </TabsTrigger>
              {/* Admin-only tabs */}
              <AdminGuard>
                <TabsTrigger
                  value="guardrails"
                  className="w-full justify-start data-[state=active]:bg-muted data-[state=active]:shadow-none rounded-md px-3 py-2"
                >
                  <Shield className="mr-2 h-4 w-4" />
                  Guardrails
                </TabsTrigger>
              </AdminGuard>
            </TabsList>
          </div>
          <div className="px-6 flex-1 overflow-y-auto pt-6 sm:pt-0">
            <TabsContent value="preferences" className="m-0">
              <PreferencesPanel />
            </TabsContent>

            {/* Personas and Prompts content - available to all users */}
            <TabsContent value="personas" className="m-0">
              <PersonasPanel />
            </TabsContent>

            <TabsContent value="prompts" className="m-0">
              <PromptsPanel />
            </TabsContent>

            {/* Admin-only content */}
            <AdminGuard>
              <TabsContent value="guardrails" className="m-0">
                <GuardrailsPanel />
              </TabsContent>
            </AdminGuard>

            {/* Fallback content for non-admin users who navigate to admin tabs */}
            <AdminGuard
              fallback={
                <>
                  <TabsContent value="guardrails" className="m-0">
                    <div className="flex flex-col items-center justify-center py-8">
                      <AlertCircle className="h-12 w-12 text-muted-foreground mb-4" />
                      <h3 className="text-lg font-medium mb-2">
                        Admin Access Required
                      </h3>
                      <p className="text-sm text-muted-foreground text-center max-w-md">
                        You need administrator privileges to access this
                        section.
                      </p>
                    </div>
                  </TabsContent>
                </>
              }
            >
              {/* Empty children prop to satisfy TypeScript */}
              <></>
            </AdminGuard>
          </div>
        </Tabs>
      </DialogContent>
    </Dialog>
  );
}
