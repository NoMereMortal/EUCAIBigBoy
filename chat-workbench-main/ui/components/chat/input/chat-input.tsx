// Copyright © Amazon.com and Affiliates: This deliverable is considered Developed Content as defined in the AWS Service
// Terms and the SOW between the parties dated 2025.

'use client';

import { useState, useRef, useEffect, useMemo, useCallback } from 'react';
import { useDropzone } from 'react-dropzone';
import { useStore } from '@/lib/store/index';
import { FileChip, FileDisplayInfo } from '@/components/chat/input/file-chip';
import { useMessageStore } from '@/lib/store/message/message-slice';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  SendHorizontal,
  Loader2,
  X,
  Feather,
  Library,
  User,
  Check,
  Paperclip,
} from 'lucide-react';
import { useUserProfile } from '@/hooks/use-user-profile';
import { ModelSelector } from '@/components/chat/input/model-selector';
import { TaskHandlerSelector } from '@/components/chat/input/task-handler-selector';
import { PromptModal } from '@/components/chat/input/prompt-modal';
import {
  FileUploader,
  FilePointer,
  LocalFileInfo,
} from '@/components/chat/input/file-uploader';
import { api, apiClient, getHeaders } from '@/lib/api/index';
import { Persona } from '@/lib/types';
import {
  DropdownMenu,
  DropdownMenuTrigger,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
} from '@/components/ui/dropdown-menu';
import { cn } from '@/lib/utils';
import { useRouter } from 'next/navigation';

interface ChatInputProps {
  chatId?: string;
}

// Helper function to extract variables from prompt template
const extractVariables = (promptContent: string): string[] => {
  const variableRegex = /\[([A-Z_]+)\]/g;
  const variables: string[] = [];
  let match;

  while ((match = variableRegex.exec(promptContent)) !== null) {
    if (!variables.includes(match[1])) {
      variables.push(match[1]);
    }
  }

  return variables;
};

export function ChatInput({ chatId }: ChatInputProps) {
  const [input, setInput] = useState('');
  const store = useStore();
  const {
    selectedPrompt,
    clearSelectedPrompt,
    selectedPersonaId,
    setSelectedPersona,
  } = store;

  // Use message store directly
  const {
    isStreaming,
    startMessageGeneration,
    error: messageError,
  } = useMessageStore();

  // Get auth for user ID
  const { userProfile, getGreeting } = useUserProfile();

  // Check if chat has messages
  const hasMessages = !!chatId && chatId !== 'new';

  // Reset sending state when errors occur
  useEffect(() => {
    if (messageError) {
      setIsSending(false);
      // We don't need to display the error here
      // since it will be displayed as a message
    }
  }, [messageError]);

  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const [isSending, setIsSending] = useState(false);
  const [isFocused, setIsFocused] = useState(false);
  const [variableValues, setVariableValues] = useState<Record<string, string>>(
    {},
  );
  const [inputPosition, setInputPosition] = useState<'center' | 'bottom'>(
    hasMessages ? 'bottom' : 'center',
  );
  const [isPromptModalOpen, setIsPromptModalOpen] = useState(false);
  const [showFileUploader, setShowFileUploader] = useState(false);
  // Files that have been uploaded to the server and have pointers
  const [filePointers, setFilePointers] = useState<FilePointer[]>([]);
  // Files that have been selected but not yet uploaded
  const [selectedFiles, setSelectedFiles] = useState<LocalFileInfo[]>([]);
  // Use a ref to track if we're already processing files to avoid loops
  const processingFilesRef = useRef(false);
  // Reference for file input element
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [personas, setPersonas] = useState<Persona[]>([]);
  const [isLoadingPersonas, setIsLoadingPersonas] = useState(true);
  const router = useRouter();

  // Initialize dropzone for drag and drop functionality
  const onDrop = useCallback((acceptedFiles: File[]) => {
    // Process dropped files
    const localFiles: LocalFileInfo[] = acceptedFiles.map((file) => {
      // Create preview URLs for images
      let preview = undefined;
      if (file.type.startsWith('image/')) {
        preview = URL.createObjectURL(file);
      }
      return { file, preview_url: preview };
    });

    setSelectedFiles((prev) => [...prev, ...localFiles]);
  }, []);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    noClick: true, // Don't open file dialog on click (we handle that with the paperclip button)
    accept: {
      'image/*': [],
      'application/pdf': [],
      'text/plain': [],
      'text/csv': [],
    },
  });

  // Function to remove a file from selected files or file pointers
  const handleRemoveFile = (index: number, type: 'selected' | 'uploaded') => {
    if (type === 'selected') {
      // Remove from selected files
      setSelectedFiles((prev) => {
        // Clean up any preview URLs to avoid memory leaks
        const fileToRemove = prev[index];
        if (fileToRemove.preview_url) {
          URL.revokeObjectURL(fileToRemove.preview_url);
        }
        return prev.filter((_, i) => i !== index);
      });
    } else {
      // Remove from file pointers
      setFilePointers((prev) => prev.filter((_, i) => i !== index));
    }
  };

  // Fetch personas from API only on client-side to avoid hydration issues
  useEffect(() => {
    // Skip API calls during server-side rendering
    if (typeof window === 'undefined') {
      return;
    }

    let isMounted = true;

    const fetchPersonas = async () => {
      try {
        setIsLoadingPersonas(true);
        // Wrap in try-catch to handle the case when the API client isn't ready
        const response = await api.getPersonas().catch((err) => {
          console.debug('API not ready yet, will retry on auth state change');
          return { personas: [] };
        });

        // Only update state if the component is still mounted
        if (isMounted && response.personas) {
          setPersonas(response.personas);
        }
      } catch (error) {
        console.error('Failed to fetch personas:', error);
        // Set empty personas array to prevent errors
        if (isMounted) {
          setPersonas([]);
        }
      } finally {
        if (isMounted) {
          setIsLoadingPersonas(false);
        }
      }
    };

    // Short delay to ensure auth is initialized
    const timer = setTimeout(() => {
      fetchPersonas();
    }, 100);

    // Cleanup function
    return () => {
      isMounted = false;
      clearTimeout(timer);
    };
  }, []);

  // Extract variables from the selected prompt using useMemo
  const promptVariables = useMemo(() => {
    return selectedPrompt ? extractVariables(selectedPrompt.content) : [];
  }, [selectedPrompt]);

  // Create computed prompt content with variables substituted
  const computedPromptContent = useMemo(() => {
    if (!selectedPrompt) return '';

    let content = selectedPrompt.content;

    // Replace variables with their values or keep as placeholders
    promptVariables.forEach((variable) => {
      const value = variableValues[variable];
      if (value && value.trim()) {
        // Replace with actual value
        content = content.replace(new RegExp(`\\[${variable}\\]`, 'g'), value);
      }
      // If no value, leave the [VARIABLE] as is for now
    });

    return content;
  }, [selectedPrompt, variableValues, promptVariables]);

  // Reset variable values and set computed content when prompt changes
  useEffect(() => {
    if (selectedPrompt) {
      const variables = extractVariables(selectedPrompt.content);
      const initialValues = Object.fromEntries(variables.map((v) => [v, '']));
      setVariableValues(initialValues);

      // If no variables, directly set the content to input
      if (variables.length === 0) {
        setInput(selectedPrompt.content);
      } else {
        // Set the initial template content
        setInput(selectedPrompt.content);
      }
    } else {
      setVariableValues({});
    }
  }, [selectedPrompt]);

  // Update input content when variables change (live substitution)
  useEffect(() => {
    if (selectedPrompt && promptVariables.length > 0) {
      setInput(computedPromptContent);
    }
  }, [computedPromptContent, selectedPrompt, promptVariables.length]);

  useEffect(() => {
    if (typeof window !== 'undefined' && textareaRef.current) {
      textareaRef.current.focus();
    }
  }, []);

  // Update position when hasMessages changes
  // Always force to bottom position if there are messages
  useEffect(() => {
    if (hasMessages) {
      setInputPosition('bottom');
    } else {
      setInputPosition('center');
    }
  }, [hasMessages]);

  // Function to upload files with a given chat ID
  const uploadSelectedFiles = async (currentChatId: string) => {
    if (selectedFiles.length === 0) return [];

    try {
      // Create FormData with chat_id and model_id
      const formData = new FormData();
      formData.append('chat_id', currentChatId);

      if (store.selectedModelId) {
        formData.append('model_id', store.selectedModelId);
      }

      // Add all files to the FormData
      selectedFiles.forEach((fileInfo) => {
        formData.append('files', fileInfo.file);
      });

      // Use our dedicated file API to upload files
      // This will handle URL construction and authentication properly
      const result = await api.file.uploadFiles(formData);
      return result.files || [];
    } catch (error) {
      console.error('Error uploading files:', error);
      return [];
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    // No input and no files - nothing to do
    if (!input.trim() && selectedFiles.length === 0) return;
    if (isStreaming) return;

    // Skip during server-side rendering
    if (typeof window === 'undefined') {
      console.debug('Cannot submit during server-side rendering');
      return;
    }

    setIsSending(true);

    try {
      // Get or create chat ID
      let currentChatId = chatId;
      if (!currentChatId || currentChatId === 'new') {
        // Create new chat
        const titlePreview =
          input.substring(0, 30) + (input.length > 30 ? '...' : '');

        if (!userProfile?.id) {
          console.error('No user ID available for creating chat');
          setIsSending(false);
          return;
        }

        // Ensure we're on the client-side before creating a chat
        if (typeof window !== 'undefined') {
          const chat = await useMessageStore
            .getState()
            .createChat(titlePreview, userProfile.id);
          currentChatId = chat.chat_id;

          // Navigate to new chat IMMEDIATELY before starting message generation
          // Use replace to avoid back button issues
          router.replace(`/chat/${currentChatId}`);

          // Give the navigation a moment to complete
          await new Promise((resolve) => setTimeout(resolve, 100));
        } else {
          console.error('Cannot create chat during server-side rendering');
          setIsSending(false);
          return;
        }
      }

      // Find the most recent assistant message in the current path to use as parent
      const currentPath = currentChatId
        ? useMessageStore.getState().activeMessagePath[currentChatId] || []
        : [];
      const messages = useMessageStore.getState().messages;

      // Walk backwards through the path to find the last assistant message
      let parentId: string | null = null;
      for (let i = currentPath.length - 1; i >= 0; i--) {
        const message = messages[currentPath[i]];
        if (message && message.kind === 'response') {
          parentId = message.message_id;
          break;
        }
      }

      // Upload any pending selected files using the current chat ID
      let newFilePointers: FilePointer[] = [];
      if (selectedFiles.length > 0 && currentChatId) {
        console.log('Uploading files for chat:', currentChatId);
        newFilePointers = await uploadSelectedFiles(currentChatId);
        setFilePointers((prevPointers) => [
          ...prevPointers,
          ...newFilePointers,
        ]);
        setSelectedFiles([]); // Clear selected files after upload
      }

      // Combine existing file pointers with any newly uploaded ones
      const allFilePointers = [...filePointers, ...newFilePointers];

      // Prepare parts for the message - always put file parts first
      const parts = [];

      // Add file pointer parts first
      allFilePointers.forEach((file) => {
        if (file.file_type === 'image') {
          parts.push({
            part_kind: 'image',
            file_id: file.file_id, // Correct field name for backend
            user_id: userProfile?.id || undefined, // Include user_id as it's required
            pointer: file.file_id, // Keep pointer for compatibility
            mime_type: file.mime_type,
            metadata: { filename: file.filename },
          });
        } else {
          parts.push({
            part_kind: 'document',
            file_id: file.file_id, // Correct field name for backend
            pointer: file.file_id, // Keep pointer for compatibility
            mime_type: file.mime_type,
            title: file.filename,
            user_id: userProfile?.id || undefined, // Include user_id if available
            metadata: { filename: file.filename },
          });
        }
      });

      // Add text part if we have input
      if (input.trim()) {
        parts.push({
          part_kind: 'text',
          content: input.trim(),
        });
      }

      // Send the message with all parts
      if (parts.length > 0 && currentChatId) {
        await startMessageGeneration(currentChatId, parts, parentId);
      }

      // Clear input and file pointers
      setInput('');
      setFilePointers([]);
      setSelectedFiles([]);
      setShowFileUploader(false);
    } catch (error) {
      console.error('Failed to send message:', error);
    } finally {
      setIsSending(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e as unknown as React.FormEvent);
    }
  };

  return (
    <div
      className={cn(
        'w-full transition-all ease-[cubic-bezier(0.34,1.56,0.64,1)] left-1/5',
        inputPosition === 'center'
          ? 'absolute top-1/2 mx-auto transform -translate-y-1/2 justify-center'
          : 'relative',
      )}
    >
      <div className={cn('flex flex-col max-w-[60%]')}>
        {!hasMessages && userProfile && (
          <div className="text-lg font-medium mb-2 text-gray-700 dark:text-card-foreground">
            {getGreeting()}
          </div>
        )}

        {/* Display selected files above the chat input */}
        {(selectedFiles.length > 0 || filePointers.length > 0) && (
          <div className="flex flex-wrap gap-2 mb-2 p-2 bg-background/50 rounded-lg border border-border/50">
            {/* Show selected files */}
            {selectedFiles.map((file, index) => (
              <FileChip
                key={`selected-${index}-${file.file.name}`}
                file={{
                  filename: file.file.name,
                  file_type: file.file.type.startsWith('image/')
                    ? 'image'
                    : 'document',
                  preview_url: file.preview_url,
                }}
                onRemove={() => handleRemoveFile(index, 'selected')}
              />
            ))}

            {/* Show uploaded file pointers */}
            {filePointers.map((file, index) => (
              <FileChip
                key={`uploaded-${index}-${file.filename}`}
                file={{
                  filename: file.filename,
                  file_type: file.file_type,
                  // preview_url is not available on FilePointer type
                }}
                onRemove={() => handleRemoveFile(index, 'uploaded')}
              />
            ))}
          </div>
        )}

        {/* Errors are now displayed as chat messages */}

        <form
          {...getRootProps()}
          onSubmit={handleSubmit}
          className={cn(
            'bg-card transition-all ease-[cubic-bezier(0.34,1.56,0.64,1)] rounded-xl',
            isFocused && 'ring-0',
            isDragActive && 'ring-2 ring-primary border-dashed',
          )}
        >
          <input {...getInputProps()} />
          {selectedPrompt && (
            <>
              <div className="flex items-center justify-between bg-primary/10 dark:bg-card-foreground px-4 py-2 rounded-t-lg">
                <div className="flex items-center gap-2">
                  <span className="text-xs font-medium text-primary">
                    Using prompt: {selectedPrompt.name}
                  </span>
                </div>
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-6 w-6 rounded-full hover:bg-card/20"
                  onClick={() => clearSelectedPrompt?.()}
                >
                  <X className="h-3 w-3" />
                  <span className="sr-only">Clear prompt</span>
                </Button>
              </div>

              {/* Variable input fields */}
              {promptVariables.length > 0 && (
                <div className="px-4 py-2 border-t border-primary/10 dark:bg-card-foreground">
                  {promptVariables.map((variable) => (
                    <div key={variable} className="mb-3">
                      <Label className="text-xs font-medium mb-1 block">
                        {variable}
                      </Label>
                      <Input
                        value={variableValues[variable] || ''}
                        onChange={(e) =>
                          setVariableValues((prev) => ({
                            ...prev,
                            [variable]: e.target.value,
                          }))
                        }
                        className="h-8 text-sm"
                        placeholder={`Enter ${variable.toLowerCase().replace(/_/g, ' ')}`}
                      />
                    </div>
                  ))}
                  <div className="h-px bg-primary/10 my-2" />
                </div>
              )}
            </>
          )}

          <div
            className={cn(
              'flex flex-col gap-2 p-2 border rounded-xl',
              selectedPrompt && 'border-t-0 rounded-t-none',
            )}
          >
            <Textarea
              ref={textareaRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              onFocus={() => setIsFocused(true)}
              onBlur={() => setIsFocused(false)}
              placeholder={
                promptVariables.length > 0
                  ? 'Variables will be substituted in the text above'
                  : hasMessages
                    ? 'Ask a follow up question...'
                    : 'How can I help you today?'
              }
              className={cn(
                'min-h-[48px] max-h-[200px] flex-1 resize-none border-0 shadow-none bg-transparent py-3 focus:ring-0 focus-visible:ring-0',
              )}
              disabled={isStreaming}
            />
            <div className="flex items-center justify-between px-1">
              <div className="flex items-center gap-3">
                <DropdownMenu>
                  <div className="flex items-center gap-1">
                    <DropdownMenuTrigger asChild>
                      <Button
                        variant="ghost"
                        size="icon"
                        className="text-blue-500 hover:text-blue-700 icon-md"
                        type="button"
                        title="Select Persona"
                      >
                        <Feather className="icon-md stroke-medium" />
                        <span className="sr-only">Select persona/style</span>
                      </Button>
                    </DropdownMenuTrigger>

                    {/* Removed persona display from here */}
                  </div>
                  <DropdownMenuContent
                    align="start"
                    className="p-2 min-w-[200px]"
                  >
                    <DropdownMenuLabel>Select Persona</DropdownMenuLabel>
                    <DropdownMenuSeparator />

                    <DropdownMenuItem
                      className="flex items-center justify-between cursor-pointer"
                      onClick={() => setSelectedPersona?.(null)}
                    >
                      <div className="flex items-center gap-2">
                        <User className="h-3.5 w-3.5 text-primary" />
                        <span>No persona</span>
                      </div>
                      {selectedPersonaId === null && (
                        <Check className="h-4 w-4 text-primary" />
                      )}
                    </DropdownMenuItem>

                    {isLoadingPersonas ? (
                      <DropdownMenuItem disabled>
                        <div className="flex items-center gap-2">
                          <Loader2 className="h-3.5 w-3.5 animate-spin" />
                          <span>Loading personas...</span>
                        </div>
                      </DropdownMenuItem>
                    ) : personas.length === 0 ? (
                      <DropdownMenuItem disabled>
                        <span>No personas available</span>
                      </DropdownMenuItem>
                    ) : (
                      personas.map((persona) => (
                        <DropdownMenuItem
                          key={persona.persona_id}
                          className="flex items-center justify-between cursor-pointer"
                          onClick={() =>
                            setSelectedPersona?.(persona.persona_id)
                          }
                        >
                          <div className="flex items-center gap-2">
                            <User className="h-3.5 w-3.5 text-primary" />
                            <span>{persona.name}</span>
                          </div>
                          {selectedPersonaId === persona.persona_id && (
                            <Check className="h-4 w-4 text-primary" />
                          )}
                        </DropdownMenuItem>
                      ))
                    )}
                  </DropdownMenuContent>
                </DropdownMenu>

                <Button
                  variant="ghost"
                  size="icon"
                  className="text-blue-500 hover:text-blue-700 icon-md"
                  type="button"
                  onClick={() => setIsPromptModalOpen(true)}
                  title="Prompt Library"
                >
                  <Library className="icon-md stroke-medium" />
                  <span className="sr-only">Prompt library</span>
                </Button>

                <Button
                  variant="ghost"
                  size="icon"
                  className="text-blue-500 hover:text-blue-700 icon-md"
                  type="button"
                  onClick={() => {
                    // Trigger file selection directly
                    fileInputRef.current?.click();
                  }}
                  title="Upload Files"
                >
                  <Paperclip className="icon-md stroke-medium" />
                  <span className="sr-only">Upload files</span>
                </Button>
                <input
                  type="file"
                  ref={fileInputRef}
                  onChange={(e) => {
                    if (e.target.files?.length) {
                      const files = Array.from(e.target.files);
                      // Use same handler as the FileUploader component
                      const localFiles: LocalFileInfo[] = files.map((file) => {
                        // Create preview URLs for images
                        let preview = undefined;
                        if (file.type.startsWith('image/')) {
                          preview = URL.createObjectURL(file);
                        }
                        return { file, preview_url: preview };
                      });
                      setSelectedFiles((prev) => [...prev, ...localFiles]);
                    }
                    // Reset the input value
                    e.target.value = '';
                  }}
                  className="hidden"
                  multiple
                  accept="image/*,application/pdf,text/plain,text/csv,text/markdown"
                />
              </div>
              <Button
                type="submit"
                size="icon"
                disabled={
                  !!(
                    (
                      isStreaming ||
                      (selectedPrompt && promptVariables.length > 0
                        ? promptVariables.some(
                            (variable) => !variableValues[variable]?.trim(),
                          )
                        : !input.trim())
                    ) // Otherwise check if input is empty
                  )
                }
                className={cn(
                  'transition-all duration-200 rounded-full bg-primary/20 hover:bg-primary/20 text-card-foreground dark:bg-background border dark:hover:bg-card/50',
                )}
              >
                {isSending ? (
                  <Loader2 className="animate-spin" />
                ) : (
                  <SendHorizontal />
                )}
                <span className="sr-only">Send</span>
              </Button>
            </div>
          </div>
        </form>
        <div className="flex justify-between items-center mt-2">
          {/* Persona display box */}
          {selectedPersonaId ? (
            <div className="px-2 py-1 text-xs font-medium rounded-md bg-primary/10 border border-primary/20 flex items-center gap-1">
              {isLoadingPersonas
                ? 'Loading...'
                : personas.find((p) => p.persona_id === selectedPersonaId)
                    ?.name || 'No persona'}
            </div>
          ) : (
            <div className="flex"> </div>
          )}
          <div className="flex items-center gap-2">
            <TaskHandlerSelector />
            <ModelSelector />
          </div>
        </div>
      </div>

      <PromptModal
        isOpen={isPromptModalOpen}
        onClose={() => setIsPromptModalOpen(false)}
      />

      {showFileUploader && (
        <div className="mt-2 bg-gray-100 dark:bg-slate-800 p-4 rounded-lg border border-primary">
          <h3 className="text-sm font-medium mb-2">Upload Files</h3>
          <FileUploader
            chatId={chatId} // Will be undefined for new chats
            modelId={store.selectedModelId || undefined}
            uploadImmediately={false} // Don't upload right away - wait for message submission
            onFilesSelected={(files) => {
              // Prevent duplicate processing and infinite loops
              if (processingFilesRef.current) return;
              processingFilesRef.current = true;

              console.log('Files selected:', files);
              // Use a timeout to break the render cycle
              setTimeout(() => {
                setSelectedFiles(files);
                processingFilesRef.current = false;
              }, 0);
            }}
            onFilesUploaded={(files) => {
              console.log('Files uploaded to server:', files);
              setFilePointers(files);
              setShowFileUploader(false);
            }}
          />

          {selectedFiles.length > 0 && (
            <div className="mt-2 pt-2 border-t border-gray-200 dark:border-gray-700">
              <p className="text-xs text-muted-foreground">
                {selectedFiles.length} file(s) selected.
                {!chatId &&
                  ' Files will be uploaded when you send your message.'}
              </p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
