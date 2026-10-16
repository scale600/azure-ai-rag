variable "location" {
  description = "Primary Azure region. Align with the existing OpenAI resource (centralus)."
  type        = string
  default     = "centralus"
}

variable "existing_openai_name" {
  description = "Existing Azure OpenAI resource to reuse via data source (not managed here)."
  type        = string
  default     = "oai-idp-rl01"
}

variable "existing_openai_rg" {
  description = "Resource group of the existing Azure OpenAI resource."
  type        = string
  default     = "idp-prototype"
}

variable "embedding_model" {
  description = "Embedding model to deploy (M1 quota gate — fails if quota denied)."
  type        = string
  default     = "text-embedding-3-small"
}

variable "embedding_model_version" {
  description = "Version of the embedding model. Confirm availability in centralus before apply."
  type        = string
  default     = "1"
}

variable "chat_model_deployment" {
  description = "Name of the already-deployed chat model on the existing OpenAI resource."
  type        = string
  default     = "gpt-4.1-mini"
}
