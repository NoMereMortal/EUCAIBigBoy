// Copyright © Amazon.com and Affiliates: This deliverable is considered Developed Content as defined in the AWS Service
// Terms and the SOW between the parties dated 2025.

'use client';

import { useState, useEffect } from 'react';
import { Button } from '@/components/ui/button';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Plus, Pencil, Trash2, X } from 'lucide-react';
import { api } from '@/lib/api/index';
import {
  GuardrailInfo,
  GuardrailDetail,
  GuardrailCreate,
  GuardrailUpdate,
  GuardrailContentFilter,
  GuardrailDeniedTopic,
  GuardrailPiiEntity,
  ContentFilterType,
  FilterStrength,
  PiiEntityType,
  PiiAction,
} from '@/lib/types';

import { BasicInfoForm } from '@/components/settings/guardrail/basic-info-form';
import { ContentFiltersForm } from '@/components/settings/guardrail/content-filters-form';
import { WordFiltersForm } from '@/components/settings/guardrail/word-filters-form';
import { DeniedTopicsForm } from '@/components/settings/guardrail/denied-topics-form';
import { PiiEntitiesForm } from '@/components/settings/guardrail/pii-entities-form';
import { FormTabs } from '@/components/settings/guardrail/form-tabs';
import { GuardrailDetailView } from '@/components/settings/guardrail/guardrail-detail';

export function GuardrailsPanel() {
  const [guardrails, setGuardrails] = useState<GuardrailInfo[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedGuardrail, setSelectedGuardrail] =
    useState<GuardrailDetail | null>(null);

  // Form state for creating/editing guardrails
  const [isEditing, setIsEditing] = useState(false);
  const [editingGuardrail, setEditingGuardrail] =
    useState<GuardrailDetail | null>(null);
  const [formMode, setFormMode] = useState<
    'basic' | 'content' | 'wordFilters' | 'deniedTopics' | 'pii'
  >('basic');
  const [formData, setFormData] = useState<GuardrailCreate>({
    name: '',
    description: '',
    content_filters: [],
    denied_topics: [],
    word_filters: [],
    pii_entities: [],
    blocked_input_messaging: 'Your request was blocked by content filtering.',
    blocked_output_messaging: 'The response was blocked by content filtering.',
  });

  // Fetch guardrails from API
  const fetchGuardrails = async () => {
    try {
      setIsLoading(true);
      setError(null);
      const response = await api.getGuardrails();
      setGuardrails(response.guardrails);
    } catch (error) {
      console.error('Failed to fetch guardrails:', error);
      setError('Failed to load guardrails. Please try again.');
    } finally {
      setIsLoading(false);
    }
  };

  // Fetch single guardrail details
  const fetchGuardrailDetail = async (guardrailId: string) => {
    try {
      setIsLoading(true);
      setError(null);
      const detail = await api.getGuardrail(guardrailId);
      setSelectedGuardrail(detail);
      return detail;
    } catch (error) {
      console.error('Failed to fetch guardrail details:', error);
      setError('Failed to load guardrail details. Please try again.');
      return null;
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchGuardrails();
  }, []);

  // Handle form input changes
  const handleInputChange = (
    e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>,
  ) => {
    const { name, value } = e.target;
    setFormData((prev) => ({ ...prev, [name]: value }));
  };

  // Start editing a guardrail
  const handleEdit = async (guardrail: GuardrailInfo | GuardrailDetail) => {
    let detail: GuardrailDetail | null;

    if ('content_filters' in guardrail) {
      // We already have the detail view
      detail = guardrail as GuardrailDetail;
    } else {
      // We need to fetch the details
      detail = await fetchGuardrailDetail(guardrail.id);
    }

    if (!detail) return;

    setEditingGuardrail(detail);
    setFormData({
      name: detail.name,
      description: detail.description,
      content_filters: detail.content_filters,
      denied_topics: detail.denied_topics,
      word_filters: detail.word_filters,
      pii_entities: detail.pii_entities,
      blocked_input_messaging: detail.blocked_input_messaging,
      blocked_output_messaging: detail.blocked_output_messaging,
    });
    setFormMode('basic');
    setIsEditing(true);
  };

  // Start creating a new guardrail
  const handleCreate = () => {
    setEditingGuardrail(null);
    setFormData({
      name: '',
      description: '',
      content_filters: [
        {
          type: ContentFilterType.SEXUAL,
          input_strength: FilterStrength.MEDIUM,
          output_strength: FilterStrength.MEDIUM,
        },
      ],
      denied_topics: [],
      word_filters: [],
      pii_entities: [],
      blocked_input_messaging: 'Your request was blocked by content filtering.',
      blocked_output_messaging:
        'The response was blocked by content filtering.',
    });
    setFormMode('basic');
    setIsEditing(true);
  };

  // Content filter handlers
  const handleAddContentFilter = () => {
    setFormData((prev) => ({
      ...prev,
      content_filters: [
        ...prev.content_filters,
        {
          type: ContentFilterType.SEXUAL,
          input_strength: FilterStrength.MEDIUM,
          output_strength: FilterStrength.MEDIUM,
        },
      ],
    }));
  };

  const handleContentFilterChange = (
    index: number,
    field: keyof GuardrailContentFilter,
    value: any,
  ) => {
    setFormData((prev) => {
      const updatedFilters = [...prev.content_filters];
      updatedFilters[index] = {
        ...updatedFilters[index],
        [field]: value,
      };
      return { ...prev, content_filters: updatedFilters };
    });
  };

  const handleRemoveContentFilter = (index: number) => {
    setFormData((prev) => ({
      ...prev,
      content_filters: prev.content_filters.filter((_, i) => i !== index),
    }));
  };

  // Word filter handlers
  const handleAddWordFilter = () => {
    setFormData((prev) => ({
      ...prev,
      word_filters: [...prev.word_filters, { text: '' }],
    }));
  };

  const handleWordFilterChange = (index: number, value: string) => {
    setFormData((prev) => {
      const updatedFilters = [...prev.word_filters];
      updatedFilters[index] = { text: value };
      return { ...prev, word_filters: updatedFilters };
    });
  };

  const handleRemoveWordFilter = (index: number) => {
    setFormData((prev) => ({
      ...prev,
      word_filters: prev.word_filters.filter((_, i) => i !== index),
    }));
  };

  // Denied topics handlers
  const handleAddDeniedTopic = () => {
    setFormData((prev) => ({
      ...prev,
      denied_topics: [
        ...prev.denied_topics,
        { name: '', definition: '', examples: [] },
      ],
    }));
  };

  const handleDeniedTopicChange = (
    index: number,
    field: keyof GuardrailDeniedTopic,
    value: any,
  ) => {
    setFormData((prev) => {
      const updatedTopics = [...prev.denied_topics];
      updatedTopics[index] = {
        ...updatedTopics[index],
        [field]: value,
      };
      return { ...prev, denied_topics: updatedTopics };
    });
  };

  const handleExamplesChange = (index: number, value: string) => {
    const examples = value
      .split(',')
      .map((ex) => ex.trim())
      .filter(Boolean);
    handleDeniedTopicChange(index, 'examples', examples);
  };

  const handleRemoveDeniedTopic = (index: number) => {
    setFormData((prev) => ({
      ...prev,
      denied_topics: prev.denied_topics.filter((_, i) => i !== index),
    }));
  };

  // PII entity handlers
  const handleAddPiiEntity = () => {
    setFormData((prev) => ({
      ...prev,
      pii_entities: [
        ...prev.pii_entities,
        { type: PiiEntityType.EMAIL, action: PiiAction.ANONYMIZE },
      ],
    }));
  };

  const handlePiiEntityChange = (
    index: number,
    field: keyof GuardrailPiiEntity,
    value: any,
  ) => {
    setFormData((prev) => {
      const updatedEntities = [...prev.pii_entities];
      updatedEntities[index] = {
        ...updatedEntities[index],
        [field]: value,
      };
      return { ...prev, pii_entities: updatedEntities };
    });
  };

  const handleRemovePiiEntity = (index: number) => {
    setFormData((prev) => ({
      ...prev,
      pii_entities: prev.pii_entities.filter((_, i) => i !== index),
    }));
  };

  // Save guardrail (create or update)
  const handleSave = async () => {
    try {
      setIsLoading(true);
      if (editingGuardrail) {
        // Update existing guardrail
        await api.updateGuardrail(
          editingGuardrail.id,
          formData as GuardrailUpdate,
        );
      } else {
        // Create new guardrail
        await api.createGuardrail(formData);
      }
      // Refresh guardrails list
      await fetchGuardrails();
      setIsEditing(false);
      setSelectedGuardrail(null);
    } catch (error) {
      console.error('Failed to save guardrail:', error);
      setError('Failed to save guardrail. Please try again.');
    } finally {
      setIsLoading(false);
    }
  };

  // Delete a guardrail
  const handleDelete = async (guardrailId: string) => {
    if (!confirm('Are you sure you want to delete this guardrail?')) return;

    try {
      setIsLoading(true);
      await api.deleteGuardrail(guardrailId);
      await fetchGuardrails();
      setSelectedGuardrail(null);
    } catch (error) {
      console.error('Failed to delete guardrail:', error);
      setError('Failed to delete guardrail. Please try again.');
    } finally {
      setIsLoading(false);
    }
  };

  // Publish a guardrail version
  const handlePublish = async (guardrailId: string) => {
    const description = prompt(
      'Enter a description for this version (optional):',
    );

    try {
      setIsLoading(true);
      await api.publishGuardrailVersion(guardrailId, description || undefined);
      // Refresh the selected guardrail to show the new version
      if (selectedGuardrail && selectedGuardrail.id === guardrailId) {
        await fetchGuardrailDetail(guardrailId);
      }
    } catch (error) {
      console.error('Failed to publish guardrail version:', error);
      setError('Failed to publish guardrail version. Please try again.');
    } finally {
      setIsLoading(false);
    }
  };

  // View guardrail details
  const handleViewDetails = async (guardrail: GuardrailInfo) => {
    await fetchGuardrailDetail(guardrail.id);
  };

  // Cancel editing
  const handleCancel = () => {
    setIsEditing(false);
  };

  // Render form content based on selected tab
  const renderFormContent = () => {
    switch (formMode) {
      case 'basic':
        return (
          <BasicInfoForm
            formData={formData}
            handleInputChange={handleInputChange}
          />
        );

      case 'content':
        return (
          <ContentFiltersForm
            formData={formData}
            handleAddContentFilter={handleAddContentFilter}
            handleContentFilterChange={handleContentFilterChange}
            handleRemoveContentFilter={handleRemoveContentFilter}
          />
        );

      case 'wordFilters':
        return (
          <WordFiltersForm
            formData={formData}
            handleAddWordFilter={handleAddWordFilter}
            handleWordFilterChange={handleWordFilterChange}
            handleRemoveWordFilter={handleRemoveWordFilter}
          />
        );

      case 'deniedTopics':
        return (
          <DeniedTopicsForm
            formData={formData}
            handleAddDeniedTopic={handleAddDeniedTopic}
            handleDeniedTopicChange={handleDeniedTopicChange}
            handleExamplesChange={handleExamplesChange}
            handleRemoveDeniedTopic={handleRemoveDeniedTopic}
          />
        );

      case 'pii':
        return (
          <PiiEntitiesForm
            formData={formData}
            handleAddPiiEntity={handleAddPiiEntity}
            handlePiiEntityChange={handlePiiEntityChange}
            handleRemovePiiEntity={handleRemovePiiEntity}
          />
        );

      default:
        return null;
    }
  };

  // Render form for creating/editing
  if (isEditing) {
    return (
      <div className="grid gap-4">
        <div className="flex items-center justify-between">
          <h3 className="text-lg font-medium">
            {editingGuardrail ? 'Edit Guardrail' : 'Create New Guardrail'}
          </h3>
          <Button variant="ghost" size="sm" onClick={handleCancel}>
            <X />
          </Button>
        </div>

        <FormTabs formMode={formMode} setFormMode={setFormMode} />
        {renderFormContent()}

        {error && <p className="text-sm text-red-500">{error}</p>}

        <div className="flex justify-end gap-2 mt-2">
          <Button variant="outline" onClick={handleCancel}>
            Cancel
          </Button>
          <Button onClick={handleSave} disabled={isLoading}>
            {isLoading ? 'Saving...' : 'Save Guardrail'}
          </Button>
        </div>
      </div>
    );
  }

  // Render guardrail details
  if (selectedGuardrail) {
    return (
      <GuardrailDetailView
        guardrail={selectedGuardrail}
        handleEdit={handleEdit}
        handlePublish={handlePublish}
        onBackClick={() => setSelectedGuardrail(null)}
      />
    );
  }

  // Render list of guardrails
  return (
    <div className="grid gap-4">
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-medium">Content Guardrails</h3>
        <Button onClick={handleCreate} size="sm">
          <Plus className=" mr-1" />
          New Guardrail
        </Button>
      </div>

      {error && <p className="text-sm text-red-500">{error}</p>}

      {isLoading ? (
        <p className="text-sm text-muted-foreground">Loading guardrails...</p>
      ) : guardrails.length === 0 ? (
        <p className="text-sm text-muted-foreground">
          No guardrails available. Create one to get started.
        </p>
      ) : (
        <ScrollArea className="h-[300px] pr-4">
          <div className="grid gap-3">
            {guardrails.map((guardrail) => (
              <div key={guardrail.id} className="border rounded-md p-3 bg-card">
                <div className="flex items-start justify-between">
                  <div
                    className="cursor-pointer grow"
                    onClick={() => handleViewDetails(guardrail)}
                  >
                    <h4 className="font-medium">{guardrail.name}</h4>
                    <p className="text-sm text-muted-foreground">
                      {guardrail.description}
                    </p>
                  </div>
                  <div className="flex gap-1">
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => handleEdit(guardrail)}
                    >
                      <Pencil />
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => handleDelete(guardrail.id)}
                    >
                      <Trash2 />
                    </Button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </ScrollArea>
      )}
    </div>
  );
}
