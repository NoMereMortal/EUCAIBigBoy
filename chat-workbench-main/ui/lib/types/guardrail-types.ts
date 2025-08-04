// Copyright © Amazon.com and Affiliates: This deliverable is considered Developed Content as defined in the AWS Service
// Terms and the SOW between the parties dated 2025.

// Guardrail and content filtering types

// Content filter type enums
export enum ContentFilterType {
  SEXUAL = 'SEXUAL',
  VIOLENCE = 'VIOLENCE',
  HATE = 'HATE',
  INSULTS = 'INSULTS',
  MISCONDUCT = 'MISCONDUCT',
  PROMPT_ATTACK = 'PROMPT_ATTACK',
}

export enum FilterStrength {
  NONE = 'NONE',
  LOW = 'LOW',
  MEDIUM = 'MEDIUM',
  HIGH = 'HIGH',
}

export enum FilterAction {
  BLOCK = 'BLOCK',
  NONE = 'NONE',
}

export enum PiiAction {
  BLOCK = 'BLOCK',
  ANONYMIZE = 'ANONYMIZE',
  NONE = 'NONE',
}

export enum PiiEntityType {
  EMAIL = 'EMAIL',
  PHONE = 'PHONE',
  ADDRESS = 'ADDRESS',
  NAME = 'NAME',
  AGE = 'AGE',
  SSN = 'US_SOCIAL_SECURITY_NUMBER',
  CREDIT_CARD = 'CREDIT_DEBIT_CARD_NUMBER',
  CREDIT_CARD_CVV = 'CREDIT_DEBIT_CARD_CVV',
  CREDIT_CARD_EXPIRY = 'CREDIT_DEBIT_CARD_EXPIRY',
  BANK_ACCOUNT = 'US_BANK_ACCOUNT_NUMBER',
  BANK_ROUTING = 'US_BANK_ROUTING_NUMBER',
  IP_ADDRESS = 'IP_ADDRESS',
  PASSPORT = 'US_PASSPORT_NUMBER',
  DRIVER_ID = 'DRIVER_ID',
  LICENSE_PLATE = 'LICENSE_PLATE',
  VIN = 'VEHICLE_IDENTIFICATION_NUMBER',
  MAC_ADDRESS = 'MAC_ADDRESS',
  URL = 'URL',
  USERNAME = 'USERNAME',
  PASSWORD = 'PASSWORD', // pragma: allowlist secret
  PIN = 'PIN',
  AWS_ACCESS_KEY = 'AWS_ACCESS_KEY',
  AWS_SECRET_KEY = 'AWS_SECRET_KEY', // pragma: allowlist secret
}

// Guardrail configuration interfaces
export interface GuardrailContentFilter {
  type: ContentFilterType;
  input_strength: FilterStrength;
  output_strength: FilterStrength;
}

export interface GuardrailDeniedTopic {
  name: string;
  definition: string;
  examples: string[];
}

export interface GuardrailWordFilter {
  text: string;
}

export interface GuardrailPiiEntity {
  type: PiiEntityType;
  action: PiiAction;
}

export interface GuardrailCreate {
  name: string;
  description: string;
  content_filters: GuardrailContentFilter[];
  denied_topics: GuardrailDeniedTopic[];
  word_filters: GuardrailWordFilter[];
  pii_entities: GuardrailPiiEntity[];
  blocked_input_messaging: string;
  blocked_output_messaging: string;
}

export interface GuardrailUpdate {
  name?: string;
  description?: string;
  content_filters?: GuardrailContentFilter[];
  denied_topics?: GuardrailDeniedTopic[];
  word_filters?: GuardrailWordFilter[];
  pii_entities?: GuardrailPiiEntity[];
  blocked_input_messaging?: string;
  blocked_output_messaging?: string;
}

export interface GuardrailVersion {
  version: string;
  created_at: string;
}

export interface GuardrailInfo {
  id: string;
  name: string;
  description: string;
  created_at: string;
  versions: GuardrailVersion[];
  current_version?: string;
}

export interface GuardrailDetail extends GuardrailInfo {
  content_filters: GuardrailContentFilter[];
  denied_topics: GuardrailDeniedTopic[];
  word_filters: GuardrailWordFilter[];
  pii_entities: GuardrailPiiEntity[];
  blocked_input_messaging: string;
  blocked_output_messaging: string;
}

export interface ListGuardrailsResponse {
  guardrails: GuardrailInfo[];
  last_evaluated_key: any | null;
}
