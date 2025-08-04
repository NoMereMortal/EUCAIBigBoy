// Copyright © Amazon.com and Affiliates: This deliverable is considered Developed Content as defined in the AWS Service
// Terms and the SOW between the parties dated 2025.

'use client';

import { useState, useEffect } from 'react';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { useStore } from '@/lib/store/index';
import { cn } from '@/lib/utils';
import { User } from 'lucide-react';
import { api } from '@/lib/api/index';
import { Persona } from '@/lib/types';

export function PersonaSelector() {
  const { selectedPersonaId, setSelectedPersona } = useStore();
  const [isChanging, setIsChanging] = useState(false);
  const [personas, setPersonas] = useState<Persona[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  // Fetch personas from API
  useEffect(() => {
    const fetchPersonas = async () => {
      try {
        setIsLoading(true);
        const response = await api.getPersonas();
        setPersonas(response.personas);
      } catch (error) {
        console.error('Failed to fetch personas:', error);
      } finally {
        setIsLoading(false);
      }
    };

    fetchPersonas();
  }, []);

  // Animation when persona changes
  useEffect(() => {
    if (selectedPersonaId) {
      setIsChanging(true);
      const timer = setTimeout(() => setIsChanging(false), 500);
      return () => clearTimeout(timer);
    }
  }, [selectedPersonaId]);

  return (
    <div className={cn('transition-all duration-300')}>
      <div>
        <Select
          value={selectedPersonaId || 'none'}
          onValueChange={(value) => {
            if (setSelectedPersona)
              setSelectedPersona(value === 'none' ? null : value);
          }}
        >
          <SelectTrigger
            className={cn(
              'h-10 px-3  transition-all rounded-lg bg-card border',
            )}
          >
            <div className="flex items-center gap-2 w-full overflow-hidden">
              <SelectValue placeholder="Select persona" className="truncate" />
            </div>
          </SelectTrigger>
          <SelectContent className="animate-fade-in">
            <SelectItem
              value="none"
              className="hover:bg-accent transition-colors cursor-pointer"
            >
              <div className="flex items-center justify-between w-full pr-2">
                <span>No persona</span>
              </div>
            </SelectItem>

            {isLoading ? (
              <SelectItem value="loading" disabled className="opacity-50">
                <div className="flex items-center justify-between w-full pr-2">
                  <span>Loading personas...</span>
                </div>
              </SelectItem>
            ) : personas.length === 0 ? (
              <SelectItem value="none" disabled className="opacity-50">
                <div className="flex items-center justify-between w-full pr-2">
                  <span>No personas available</span>
                </div>
              </SelectItem>
            ) : (
              personas.map((persona) => (
                <SelectItem
                  key={persona.persona_id}
                  value={persona.persona_id}
                  className="hover:bg-accent transition-colors cursor-pointer"
                >
                  <div className="flex items-center justify-between w-full">
                    <span className="truncate">{persona.name}</span>
                  </div>
                </SelectItem>
              ))
            )}
          </SelectContent>
        </Select>
      </div>
    </div>
  );
}
