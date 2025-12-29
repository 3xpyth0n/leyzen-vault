<template>
  <div class="admin-sso-view-container">
    <div class="admin-sso-providers">
      <h1>Authentication Methods</h1>

      <div v-if="loading" class="loading">Loading providers...</div>
      <div v-else-if="error" class="error">{{ error }}</div>

      <div class="providers-section">
        <div class="section-header">
          <h2>Authentication Methods</h2>
          <button @click="openCreateModal" class="btn btn-primary">
            Add Provider
          </button>
        </div>

        <div v-if="providers.length === 0" class="empty-state">
          <p>No SSO providers configured. Create one to get started.</p>
        </div>

        <div class="providers-list">
          <div
            class="provider-card password-auth-card"
            :class="{ 'provider-inactive': !passwordAuthEnabled }"
          >
            <div class="provider-header">
              <div class="provider-info">
                <h3>Password Authentication</h3>
                <span class="provider-type">SYSTEM</span>
              </div>
              <div class="provider-actions">
                <div class="toggle-container">
                  <label class="toggle-label">
                    <div
                      class="toggle-switch"
                      :class="{ active: passwordAuthEnabled }"
                      @click="togglePasswordAuth"
                    >
                      <div class="toggle-slider"></div>
                    </div>
                  </label>
                </div>
              </div>
            </div>
            <div class="provider-details">
              <p>
                Default authentication method using email/username and password
              </p>
            </div>
          </div>

          <div
            class="provider-card password-auth-card"
            :class="{ 'provider-inactive': !allowSignupEnabled }"
          >
            <div class="provider-header">
              <div class="provider-info">
                <h3>Allow Public Signup</h3>
                <span class="provider-type">SYSTEM</span>
              </div>
              <div class="provider-actions">
                <div class="toggle-container">
                  <label class="toggle-label">
                    <div
                      class="toggle-switch"
                      :class="{ active: allowSignupEnabled }"
                      @click="toggleAllowSignup"
                    >
                      <div class="toggle-slider"></div>
                    </div>
                  </label>
                </div>
              </div>
            </div>
            <div class="provider-details">
              <p>
                When disabled, only admins can create user accounts via
                invitations.
              </p>
            </div>
          </div>

          <div
            v-for="provider in providers"
            :key="provider.id"
            class="provider-card"
            :class="{ 'provider-inactive': !provider.is_active }"
          >
            <div class="provider-header">
              <div class="provider-info">
                <h3>{{ provider.name }}</h3>
                <span class="provider-type">{{
                  provider.provider_type.toUpperCase()
                }}</span>
              </div>
              <div class="provider-actions">
                <div class="toggle-container">
                  <label class="toggle-label">
                    <div
                      class="toggle-switch"
                      :class="{ active: provider.is_active }"
                      @click="toggleProvider(provider)"
                    >
                      <div class="toggle-slider"></div>
                    </div>
                  </label>
                </div>
                <button
                  @click="editProvider(provider)"
                  class="btn btn-small btn-secondary"
                >
                  Edit
                </button>
                <button
                  @click="deleteProvider(provider.id)"
                  class="btn btn-small btn-danger"
                >
                  Delete
                </button>
              </div>
            </div>
            <div class="provider-details">
              <p><strong>ID:</strong> {{ provider.id }}</p>
              <p>
                <strong>Created:</strong> {{ formatDate(provider.created_at) }}
              </p>
            </div>
          </div>
        </div>
      </div>

      <div class="domain-rules-section">
        <div class="section-header">
          <h2>Domain Rules</h2>
          <div class="button-group">
            <button @click="showDomainRuleModal = true" class="btn btn-primary">
              Add Domain Rule
            </button>
            <button @click="loadDomainRules" class="btn btn-secondary">
              Refresh Rules
            </button>
          </div>
        </div>

        <div v-if="domainRulesLoading" class="loading">
          Loading domain rules...
        </div>
        <div v-else-if="domainRulesError" class="error">
          {{ domainRulesError }}
        </div>
        <div v-else-if="domainRules.length === 0" class="empty-state">
          <p>No domain rules configured</p>
        </div>
        <div v-else class="domain-rules-list">
          <div
            v-for="rule in domainRules"
            :key="rule.id"
            class="domain-rule-item"
          >
            <div class="domain-rule-info">
              <span class="domain-rule-pattern">{{ rule.domain_pattern }}</span>
              <span
                class="domain-rule-status"
                :class="{
                  active: rule.is_active,
                  inactive: !rule.is_active,
                }"
              >
                {{ rule.is_active ? "Active" : "Inactive" }}
              </span>
            </div>
            <div class="domain-rule-actions">
              <button
                @click="editDomainRule(rule)"
                class="btn btn-small btn-secondary"
              >
                Edit
              </button>
              <button
                @click="deleteDomainRule(rule.id)"
                class="btn btn-small btn-danger"
              >
                Delete
              </button>
            </div>
          </div>
        </div>
      </div>

      <Teleport v-if="showModal" to="body">
        <div class="modal-overlay" @click="closeModal">
          <div class="modal modal-wide" @click.stop>
            <div class="modal-header">
              <h3>{{ editingProvider ? "Edit Provider" : "Add Provider" }}</h3>
              <button
                @click="closeModal"
                class="modal-close-btn"
                aria-label="Close"
                type="button"
              >
                ×
              </button>
            </div>

            <div class="modal-body">
              <form @submit.prevent="handleSaveProvider" class="modal-form">
                <div class="form-group">
                  <label for="provider-name">Name *</label>
                  <input
                    id="provider-name"
                    v-model="form.name"
                    type="text"
                    required
                    autocomplete="off"
                    placeholder="e.g., Google SSO, Azure AD"
                  />
                </div>

                <div class="form-group">
                  <label for="provider-type">Provider Type *</label>
                  <CustomSelect
                    id="provider-type"
                    v-model="form.provider_type"
                    :options="providerTypeOptions"
                    :disabled="editingProvider !== null"
                    @change="onProviderTypeChange"
                    placeholder="Select provider..."
                  />
                </div>

                <div
                  v-if="form.provider_type === 'google'"
                  class="config-section"
                >
                  <h3>Google Configuration</h3>
                  <p class="config-description">
                    Configure Google OAuth2. You'll need to create OAuth
                    credentials in the
                    <a
                      href="https://console.cloud.google.com"
                      target="_blank"
                      rel="noopener noreferrer"
                    >
                      Google Cloud Console
                    </a>
                    and set the redirect URI to:
                    <code>{{ getRedirectUri() }}</code>
                  </p>
                  <div class="form-group">
                    <label for="google-client-id">Google Client ID *</label>
                    <input
                      id="google-client-id"
                      v-model="form.config.client_id"
                      type="text"
                      required
                      autocomplete="off"
                      placeholder="xxxxx.apps.googleusercontent.com"
                    />
                  </div>
                  <div class="form-group">
                    <label for="google-client-secret"
                      >Google Client Secret *</label
                    >
                    <input
                      id="google-client-secret"
                      v-model="form.config.client_secret"
                      type="password"
                      required
                      autocomplete="new-password"
                      placeholder="GOCSPX-xxxxx"
                    />
                  </div>
                </div>

                <div
                  v-if="form.provider_type === 'microsoft'"
                  class="config-section"
                >
                  <h3>Microsoft Entra Configuration</h3>
                  <p class="config-description">
                    Configure Microsoft Entra ID (Azure AD) using OpenID
                    Connect.
                  </p>
                  <div class="form-group">
                    <label for="microsoft-tenant-id">Tenant ID *</label>
                    <input
                      id="microsoft-tenant-id"
                      v-model="form.config.tenant_id"
                      type="text"
                      required
                      autocomplete="off"
                      placeholder="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx or common"
                    />
                    <small
                      >Use "common" for multi-tenant or your specific tenant
                      ID</small
                    >
                  </div>
                  <div class="form-group">
                    <label for="microsoft-client-id"
                      >Client ID (Application ID) *</label
                    >
                    <input
                      id="microsoft-client-id"
                      v-model="form.config.client_id"
                      type="text"
                      required
                      autocomplete="off"
                      placeholder="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
                    />
                  </div>
                  <div class="form-group">
                    <label for="microsoft-client-secret">Client Secret *</label>
                    <input
                      id="microsoft-client-secret"
                      v-model="form.config.client_secret"
                      type="password"
                      required
                      autocomplete="new-password"
                      placeholder="Client secret value"
                    />
                  </div>
                </div>

                <div
                  v-if="form.provider_type === 'slack'"
                  class="config-section"
                >
                  <h3>Slack Configuration</h3>
                  <p class="config-description">
                    Configure Slack OAuth2. Create an app at
                    <a
                      href="https://api.slack.com/apps"
                      target="_blank"
                      rel="noopener noreferrer"
                    >
                      api.slack.com/apps
                    </a>
                    and set the redirect URI to:
                    <code>{{ getRedirectUri() }}</code>
                  </p>
                  <div class="form-group">
                    <label for="slack-client-id">Slack Client ID *</label>
                    <input
                      id="slack-client-id"
                      v-model="form.config.client_id"
                      type="text"
                      required
                      autocomplete="off"
                      placeholder="1234567890.1234567890"
                    />
                  </div>
                  <div class="form-group">
                    <label for="slack-client-secret"
                      >Slack Client Secret *</label
                    >
                    <input
                      id="slack-client-secret"
                      v-model="form.config.client_secret"
                      type="password"
                      required
                      autocomplete="new-password"
                      placeholder="Client secret"
                    />
                  </div>
                </div>

                <div
                  v-if="form.provider_type === 'discord'"
                  class="config-section"
                >
                  <h3>Discord Configuration</h3>
                  <p class="config-description">
                    Configure Discord OAuth2. Create an application at
                    <a
                      href="https://discord.com/developers/applications"
                      target="_blank"
                      rel="noopener noreferrer"
                    >
                      discord.com/developers
                    </a>
                    and set the redirect URI to:
                    <code>{{ getRedirectUri() }}</code>
                  </p>
                  <div class="form-group">
                    <label for="discord-client-id">Discord Client ID *</label>
                    <input
                      id="discord-client-id"
                      v-model="form.config.client_id"
                      type="text"
                      required
                      autocomplete="off"
                      placeholder="123456789012345678"
                    />
                  </div>
                  <div class="form-group">
                    <label for="discord-client-secret"
                      >Discord Client Secret *</label
                    >
                    <input
                      id="discord-client-secret"
                      v-model="form.config.client_secret"
                      type="password"
                      required
                      autocomplete="new-password"
                      placeholder="Client secret"
                    />
                  </div>
                </div>

                <div
                  v-if="form.provider_type === 'gitlab'"
                  class="config-section"
                >
                  <h3>GitLab Configuration</h3>
                  <p class="config-description">
                    Configure GitLab OAuth2. Create an application in your
                    GitLab instance (Settings → Applications) and set the
                    redirect URI to:
                    <code>{{ getRedirectUri() }}</code>
                  </p>
                  <div class="form-group">
                    <label for="gitlab-instance-url">GitLab Instance URL</label>
                    <input
                      id="gitlab-instance-url"
                      v-model="form.config.instance_url"
                      type="url"
                      autocomplete="off"
                      placeholder="https://gitlab.com (default)"
                    />
                    <small
                      >Leave empty for gitlab.com, or enter your self-hosted
                      GitLab URL</small
                    >
                  </div>
                  <div class="form-group">
                    <label for="gitlab-client-id"
                      >GitLab Application ID *</label
                    >
                    <input
                      id="gitlab-client-id"
                      v-model="form.config.client_id"
                      type="text"
                      required
                      autocomplete="off"
                      placeholder="Application ID"
                    />
                  </div>
                  <div class="form-group">
                    <label for="gitlab-client-secret">GitLab Secret *</label>
                    <input
                      id="gitlab-client-secret"
                      v-model="form.config.client_secret"
                      type="password"
                      required
                      autocomplete="new-password"
                      placeholder="Secret"
                    />
                  </div>
                </div>

                <div
                  v-if="form.provider_type === 'oidc'"
                  class="config-section"
                >
                  <h3>OIDC (Generic) Configuration</h3>
                  <p class="config-description">
                    Configure a generic OpenID Connect provider. OIDC discovery
                    will be used to find endpoints automatically.
                  </p>
                  <div class="form-group">
                    <label for="oidc-issuer-url">Issuer URL *</label>
                    <input
                      id="oidc-issuer-url"
                      v-model="form.config.issuer_url"
                      type="url"
                      required
                      autocomplete="off"
                      placeholder="https://idp.example.com"
                    />
                    <small>OIDC discovery will be used to find endpoints</small>
                  </div>
                  <div class="form-group">
                    <label for="oidc-client-id">Client ID *</label>
                    <input
                      id="oidc-client-id"
                      v-model="form.config.client_id"
                      type="text"
                      required
                      autocomplete="off"
                    />
                  </div>
                  <div class="form-group">
                    <label for="oidc-client-secret">Client Secret *</label>
                    <input
                      id="oidc-client-secret"
                      v-model="form.config.client_secret"
                      type="password"
                      required
                      autocomplete="new-password"
                    />
                  </div>
                  <div class="form-group">
                    <label for="oidc-redirect-uri">Redirect URI</label>
                    <input
                      id="oidc-redirect-uri"
                      v-model="form.config.redirect_uri"
                      type="url"
                      autocomplete="off"
                      placeholder="Auto-generated if not provided"
                    />
                  </div>
                  <div class="form-group">
                    <label for="oidc-scopes">Scopes</label>
                    <input
                      id="oidc-scopes"
                      v-model="form.config.scopes"
                      type="text"
                      autocomplete="off"
                      placeholder="openid email profile (default)"
                    />
                  </div>
                </div>

                <div
                  v-if="form.provider_type === 'email-magic-link'"
                  class="config-section"
                >
                  <h3>Email Magic Link Configuration</h3>
                  <p class="config-description">
                    Users will receive a magic link via email to sign in. No
                    password required. Make sure email (SMTP) is configured in
                    system settings.
                  </p>

                  <div class="smtp-status">
                    <div class="smtp-status-header">
                      <span class="smtp-status-label">SMTP Configuration:</span>
                      <button
                        @click="testSMTP"
                        class="btn btn-small btn-secondary"
                        :disabled="smtpTesting"
                        type="button"
                      >
                        {{ smtpTesting ? "Testing..." : "Test SMTP" }}
                      </button>
                    </div>
                    <div
                      v-if="smtpStatus !== null"
                      class="smtp-status-message"
                      :class="smtpStatus.success ? 'success' : 'error'"
                    >
                      <span class="smtp-status-icon">
                        {{ smtpStatus.success ? "✓" : "✗" }}
                      </span>
                      <span class="smtp-status-text">
                        {{
                          smtpStatus.success
                            ? smtpStatus.message
                            : smtpStatus.error
                        }}
                      </span>
                    </div>
                  </div>

                  <div class="form-group">
                    <label for="magic-link-expiry">Link Expiry (minutes)</label>
                    <input
                      id="magic-link-expiry"
                      v-model="form.config.expiry_minutes"
                      type="number"
                      min="5"
                      max="1440"
                      autocomplete="off"
                      placeholder="15 (default)"
                    />
                    <small
                      >How long the magic link remains valid (5-1440
                      minutes)</small
                    >
                  </div>
                </div>

                <div
                  v-if="form.provider_type === 'saml'"
                  class="config-section"
                >
                  <h3>SAML (Generic) Configuration</h3>
                  <div class="form-group">
                    <label for="saml-entity-id">IdP Entity ID *</label>
                    <input
                      id="saml-entity-id"
                      v-model="form.config.entity_id"
                      type="text"
                      required
                      autocomplete="off"
                      placeholder="https://idp.example.com/metadata"
                    />
                  </div>
                  <div class="form-group">
                    <label for="saml-sso-url">SSO URL *</label>
                    <input
                      id="saml-sso-url"
                      v-model="form.config.sso_url"
                      type="url"
                      required
                      autocomplete="off"
                      placeholder="https://idp.example.com/sso"
                    />
                  </div>
                  <div class="form-group">
                    <label for="saml-x509-cert">X.509 Certificate *</label>
                    <textarea
                      id="saml-x509-cert"
                      v-model="form.config.x509_cert"
                      required
                      rows="5"
                      autocomplete="off"
                      placeholder="-----BEGIN CERTIFICATE-----&#10;...&#10;-----END CERTIFICATE-----"
                    ></textarea>
                  </div>
                  <div class="form-group">
                    <label for="saml-sp-entity-id">SP Entity ID</label>
                    <input
                      id="saml-sp-entity-id"
                      v-model="form.config.sp_entity_id"
                      type="text"
                      autocomplete="off"
                      placeholder="leyzen-vault (default)"
                    />
                  </div>
                  <div class="form-group">
                    <label for="saml-acs-url">ACS URL</label>
                    <input
                      id="saml-acs-url"
                      v-model="form.config.acs_url"
                      type="url"
                      autocomplete="off"
                      placeholder="Auto-generated if not provided"
                    />
                  </div>
                </div>

                <div v-if="formError" class="error-message">
                  {{ formError }}
                </div>
                <div v-if="formSuccess" class="success-message">
                  {{ formSuccess }}
                </div>

                <div class="form-actions">
                  <button
                    type="button"
                    @click="closeModal"
                    class="btn btn-secondary"
                    :disabled="formLoading"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    class="btn btn-primary"
                    :disabled="formLoading"
                  >
                    {{ formLoading ? "Saving..." : "Save" }}
                  </button>
                </div>
              </form>
            </div>
          </div>
        </div>
      </Teleport>

      <Teleport v-if="showDeleteModal" to="body">
        <div class="modal-overlay" @click.self="closeDeleteModal">
          <div class="modal delete-modal">
            <div class="modal-header">
              <h2>Delete Provider</h2>
              <button @click="closeDeleteModal" class="modal-close">
                &times;
              </button>
            </div>
            <div class="modal-body">
              <p>
                Are you sure you want to delete the provider
                <strong>{{ providerToDelete?.name }}</strong
                >?
              </p>
              <p class="warning-text">
                This action cannot be undone. All configuration for this
                provider will be permanently deleted.
              </p>
            </div>
            <div class="modal-footer">
              <button
                type="button"
                @click="closeDeleteModal"
                class="btn btn-secondary"
                :disabled="deletingProvider"
              >
                Cancel
              </button>
              <button
                type="button"
                @click="confirmDelete"
                class="btn btn-danger"
                :disabled="deletingProvider"
              >
                {{ deletingProvider ? "Deleting..." : "Delete" }}
              </button>
            </div>
          </div>
        </div>
      </Teleport>

      <Teleport v-if="showDomainRuleModal" to="body">
        <div class="modal-overlay" @click.self="showDomainRuleModal = false">
          <div class="modal modal-wide" @click.stop>
            <div class="modal-header">
              <h3>{{ editingDomainRule ? "Edit" : "Add" }} Domain Rule</h3>
              <button
                @click="closeDomainRuleModal"
                class="modal-close-btn"
                aria-label="Close"
                type="button"
              >
                ×
              </button>
            </div>
            <div class="modal-body">
              <form @submit.prevent="handleSaveDomainRule" class="modal-form">
                <div class="form-group">
                  <label for="domain-rule-pattern">Domain Pattern:</label>
                  <input
                    id="domain-rule-pattern"
                    v-model="domainRuleForm.domain_pattern"
                    type="text"
                    required
                    :disabled="domainRuleForm.loading"
                    placeholder="example.com or *.example.com"
                    autofocus
                  />
                  <small>Use * for wildcards (e.g., *.example.com)</small>
                </div>
                <div v-if="domainRuleForm.error" class="error-message">
                  {{ domainRuleForm.error }}
                </div>
                <div v-if="domainRuleForm.success" class="success-message">
                  {{ domainRuleForm.success }}
                </div>
                <div class="form-actions">
                  <button
                    type="button"
                    @click="closeDomainRuleModal"
                    class="btn btn-secondary"
                    :disabled="domainRuleForm.loading"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    :disabled="domainRuleForm.loading"
                    class="btn btn-primary"
                  >
                    {{ domainRuleForm.loading ? "Saving..." : "Save" }}
                  </button>
                </div>
              </form>
            </div>
          </div>
        </div>
      </Teleport>

      <ConfirmationModal
        :show="showConfirmModal"
        :title="confirmModalConfig.title"
        :message="confirmModalConfig.message"
        :confirmText="confirmModalConfig.confirmText"
        :dangerous="confirmModalConfig.dangerous"
        @confirm="handleConfirmModalConfirm"
        @cancel="handleConfirmModalCancel"
        @close="handleConfirmModalCancel"
      />

      <AlertModal
        :show="showAlertModal"
        :type="alertModalConfig.type"
        :title="alertModalConfig.title"
        :message="alertModalConfig.message"
        @close="handleAlertModalClose"
        @ok="handleAlertModalClose"
      />
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from "vue";
import { admin } from "../services/api";
import { logger } from "../utils/logger.js";
import ConfirmationModal from "../components/ConfirmationModal.vue";
import AlertModal from "../components/AlertModal.vue";
import CustomSelect from "../components/CustomSelect.vue";

const loading = ref(false);
const error = ref("");
const providers = ref([]);
const showModal = ref(false);
const editingProvider = ref(null);
const formLoading = ref(false);
const formError = ref("");
const formSuccess = ref("");
const smtpTesting = ref(false);
const smtpStatus = ref(null);
const passwordAuthEnabled = ref(true);
const loadingPasswordAuth = ref(false);
const allowSignupEnabled = ref(false);
const loadingAllowSignup = ref(false);
const vaultUrl = ref(null); // VAULT_URL from settings
const showDeleteModal = ref(false);
const providerToDelete = ref(null);
const deletingProvider = ref(false);
const domainRules = ref([]);
const domainRulesLoading = ref(false);
const domainRulesError = ref("");
const showDomainRuleModal = ref(false);
const editingDomainRule = ref(null);
const domainRuleForm = ref({
  domain_pattern: "",
  loading: false,
  error: null,
  success: null,
});
const showConfirmModal = ref(false);
const confirmModalConfig = ref({
  title: "",
  message: "",
  confirmText: "Confirm",
  dangerous: false,
  onConfirm: null,
});
const showAlertModal = ref(false);
const alertModalConfig = ref({
  type: "error",
  title: "Error",
  message: "",
});

const form = ref({
  name: "",
  provider_type: "",
  config: {
    // SAML
    entity_id: "",
    sso_url: "",
    x509_cert: "",
    sp_entity_id: "",
    acs_url: "",
    // OAuth2/OIDC
    issuer_url: "",
    client_id: "",
    client_secret: "",
    authorization_url: "",
    token_url: "",
    userinfo_url: "",
    redirect_uri: "",
    scopes: "",
    // Microsoft specific
    tenant_id: "",
    // GitLab specific
    instance_url: "",
    // Email magic link
    expiry_minutes: "",
  },
});

const providerTypeOptions = [
  { value: "", label: "Select provider..." },
  { value: "email-magic-link", label: "Email Magic Link" },
  { value: "google", label: "Google" },
  { value: "microsoft", label: "Microsoft Entra" },
  { value: "slack", label: "Slack" },
  { value: "discord", label: "Discord" },
  { value: "gitlab", label: "GitLab" },
  { value: "oidc", label: "OIDC (Generic)" },
  { value: "saml", label: "SAML (Generic)" },
];

// Map provider types to technical types
const getTechnicalProviderType = (providerType) => {
  const mapping = {
    google: "oauth2",
    microsoft: "oidc",
    slack: "oauth2",
    discord: "oauth2",
    gitlab: "oauth2",
    oidc: "oidc",
    "email-magic-link": "email-magic-link",
    saml: "saml",
  };
  return mapping[providerType] || providerType;
};

// Get provider default configuration
const getProviderDefaults = (providerType) => {
  const defaults = {
    google: {
      authorization_url: "https://accounts.google.com/o/oauth2/v2/auth",
      token_url: "https://oauth2.googleapis.com/token",
      userinfo_url: "https://www.googleapis.com/oauth2/v2/userinfo",
      scopes: "openid email profile",
    },
    slack: {
      authorization_url: "https://slack.com/oauth/v2/authorize",
      token_url: "https://slack.com/api/oauth.v2.access",
      userinfo_url: "https://slack.com/api/users.identity",
      scopes: "openid email profile",
    },
    discord: {
      authorization_url: "https://discord.com/api/oauth2/authorize",
      token_url: "https://discord.com/api/oauth2/token",
      userinfo_url: "https://discord.com/api/users/@me",
      scopes: "identify email",
    },
    gitlab: {
      instance_url: "https://gitlab.com",
      authorization_url: "https://gitlab.com/oauth/authorize",
      token_url: "https://gitlab.com/oauth/token",
      userinfo_url: "https://gitlab.com/api/v4/user",
      scopes: "read_user",
    },
    microsoft: {
      scopes: "openid email profile",
    },
    oidc: {
      scopes: "openid email profile",
    },
    "email-magic-link": {
      expiry_minutes: "15",
    },
  };
  return defaults[providerType] || {};
};

// Get redirect URI for display
// Uses VAULT_URL from settings if available, otherwise falls back to window.location.origin
const getRedirectUri = () => {
  const baseUrl = vaultUrl.value || window.location.origin;
  return `${baseUrl}/api/sso/callback/{provider_id}`;
};

const loadProviders = async () => {
  loading.value = true;
  error.value = "";
  try {
    providers.value = await admin.listSSOProviders();
    await loadPasswordAuthStatus();
    await loadAllowSignupStatus();
  } catch (err) {
    error.value = err.message || "Failed to load SSO providers";
    logger.error("Failed to load SSO providers:", err);
  } finally {
    loading.value = false;
  }
};

const loadDomainRules = async () => {
  domainRulesLoading.value = true;
  domainRulesError.value = "";
  try {
    domainRules.value = await admin.listDomainRules();
  } catch (err) {
    domainRulesError.value = err.message || "Failed to load domain rules";
    logger.error("Failed to load domain rules:", err);
  } finally {
    domainRulesLoading.value = false;
  }
};

const loadPasswordAuthStatus = async () => {
  try {
    const config = await admin.getAuthConfig();
    passwordAuthEnabled.value = config.password_authentication_enabled === true;
  } catch (err) {
    logger.error("Failed to load password auth status:", err);
    // Default to true on error
    passwordAuthEnabled.value = true;
  }
};

const loadAllowSignupStatus = async () => {
  try {
    const config = await admin.getAuthConfig();
    allowSignupEnabled.value = config.allow_signup === true;
  } catch (err) {
    logger.error("Failed to load allow signup status:", err);
    // On error, default to false to be safe
    allowSignupEnabled.value = false;
  }
};

const loadVaultUrl = async () => {
  try {
    const settings = await admin.getSettings();
    if (settings.vault_url) {
      vaultUrl.value = settings.vault_url;
    }
  } catch (err) {
    logger.error("Failed to load vault_url from settings:", err);
    // Fall back to window.location.origin if vault_url is not available
    vaultUrl.value = null;
  }
};

const togglePasswordAuth = async () => {
  if (loadingPasswordAuth.value) return;

  const newValue = !passwordAuthEnabled.value;

  // Validation: if disabling, check SSO requirements
  if (!newValue) {
    const activeProviders = providers.value.filter((p) => p.is_active);
    if (activeProviders.length === 0) {
      error.value =
        "Cannot disable password authentication: at least one SSO provider must be active";
      return;
    }

    const magicLinkActive = activeProviders.some(
      (p) => p.provider_type === "email-magic-link",
    );
    if (!magicLinkActive) {
      error.value =
        "Cannot disable password authentication: Email Magic Link must be active";
      return;
    }
  }

  loadingPasswordAuth.value = true;
  const previousState = passwordAuthEnabled.value;
  passwordAuthEnabled.value = newValue;

  try {
    await admin.updateAuthConfig({
      password_authentication_enabled: newValue,
    });
    // Success - state already updated
  } catch (err) {
    // Revert on error
    passwordAuthEnabled.value = previousState;
    error.value =
      err.message || "Failed to update password authentication setting";
    logger.error("Failed to toggle password auth:", err);
  } finally {
    loadingPasswordAuth.value = false;
  }
};

const toggleAllowSignup = async () => {
  if (loadingAllowSignup.value) return;

  const newValue = !allowSignupEnabled.value;

  loadingAllowSignup.value = true;
  const previousState = allowSignupEnabled.value;
  allowSignupEnabled.value = newValue;

  try {
    await admin.updateAuthConfig({ allow_signup: newValue });
    // Success - state already updated
  } catch (err) {
    // Revert on error
    allowSignupEnabled.value = previousState;
    error.value = err.message || "Failed to update allow public signup setting";
    logger.error("Failed to toggle allow signup:", err);
  } finally {
    loadingAllowSignup.value = false;
  }
};

const resetForm = () => {
  form.value = {
    name: "",
    provider_type: "",
    config: {
      entity_id: "",
      sso_url: "",
      x509_cert: "",
      sp_entity_id: "",
      acs_url: "",
      issuer_url: "",
      client_id: "",
      client_secret: "",
      authorization_url: "",
      token_url: "",
      userinfo_url: "",
      redirect_uri: "",
      scopes: "",
    },
  };
  formError.value = "";
  formSuccess.value = "";
};

const openCreateModal = () => {
  editingProvider.value = null;
  resetForm();
  showModal.value = true;
};

// Reverse map: detect preset from technical type and config
const detectProviderPreset = (technicalType, config) => {
  if (config.provider_preset) {
    return config.provider_preset;
  }

  if (technicalType === "email-magic-link") {
    return "email-magic-link";
  } else if (technicalType === "oauth2") {
    if (config.authorization_url?.includes("google.com")) {
      return "google";
    }
    if (config.authorization_url?.includes("slack.com")) {
      return "slack";
    }
    if (config.authorization_url?.includes("discord.com")) {
      return "discord";
    }
    if (
      config.authorization_url?.includes("gitlab.com") ||
      config.instance_url
    ) {
      return "gitlab";
    }
  } else if (technicalType === "oidc") {
    if (config.issuer_url?.includes("microsoftonline.com")) {
      return "microsoft";
    }
  } else if (technicalType === "saml") {
    return "saml";
  }

  return technicalType;
};

const editProvider = async (provider) => {
  editingProvider.value = provider;

  // Detect the preset type for display
  const presetType = detectProviderPreset(
    provider.provider_type,
    provider.config || {},
  );

  // For Microsoft, extract tenant ID from issuer URL if present
  const config = { ...provider.config };
  if (presetType === "microsoft" && config.issuer_url) {
    const match = config.issuer_url.match(
      /login\.microsoftonline\.com\/([^\/]+)/,
    );
    if (match) {
      config.tenant_id = match[1];
    }
  }

  // For GitLab, extract instance_url from authorization_url if not already present
  if (
    presetType === "gitlab" &&
    !config.instance_url &&
    config.authorization_url
  ) {
    const match = config.authorization_url.match(/^(https?:\/\/[^\/]+)/);
    if (match) {
      config.instance_url = match[1];
    }
  }

  form.value = {
    name: provider.name,
    provider_type: presetType, // Use preset type for display
    // is_active is managed via toggle, not in the form
    config: config,
  };
  showModal.value = true;
};

const closeModal = () => {
  showModal.value = false;
  editingProvider.value = null;
  resetForm();
};

const handleSaveProvider = async () => {
  formLoading.value = true;
  formError.value = "";
  formSuccess.value = "";

  try {
    // Get technical provider type (map google -> oauth2, microsoft -> oidc, etc.)
    const technicalType = getTechnicalProviderType(form.value.provider_type);

    // Prepare config based on provider type
    const config = {};

    if (technicalType === "saml") {
      config.entity_id = form.value.config.entity_id;
      config.sso_url = form.value.config.sso_url;
      config.x509_cert = form.value.config.x509_cert;
      if (form.value.config.sp_entity_id) {
        config.sp_entity_id = form.value.config.sp_entity_id;
      }
      if (form.value.config.acs_url) {
        config.acs_url = form.value.config.acs_url;
      }
    } else if (technicalType === "oauth2") {
      // Email magic link is temporarily stored as oauth2
      if (form.value.provider_type === "email-magic-link") {
        // The expiry_minutes will be stored in config for future use
        if (form.value.config.expiry_minutes) {
          config.expiry_minutes =
            parseInt(form.value.config.expiry_minutes) || 15;
        }
        // For now, we need to provide dummy OAuth2 URLs since it's mapped to oauth2
        // These won't be used until full implementation
        config.authorization_url = "https://placeholder.magic-link/auth";
        config.token_url = "https://placeholder.magic-link/token";
        config.userinfo_url = "https://placeholder.magic-link/userinfo";
        config.client_id = "magic-link-placeholder";
        config.client_secret = "magic-link-placeholder";
      } else {
        config.client_id = form.value.config.client_id;
        config.client_secret = form.value.config.client_secret;

        // For GitLab, construct URLs from instance_url if provided
        if (
          form.value.provider_type === "gitlab" &&
          form.value.config.instance_url
        ) {
          const instanceUrl = form.value.config.instance_url.replace(/\/$/, "");
          config.instance_url = instanceUrl;
          config.authorization_url = `${instanceUrl}/oauth/authorize`;
          config.token_url = `${instanceUrl}/oauth/token`;
          config.userinfo_url = `${instanceUrl}/api/v4/user`;
        } else {
          config.authorization_url = form.value.config.authorization_url;
          config.token_url = form.value.config.token_url;
          config.userinfo_url = form.value.config.userinfo_url;
        }

        if (form.value.config.redirect_uri) {
          config.redirect_uri = form.value.config.redirect_uri;
        }
        if (form.value.config.scopes) {
          config.scopes = form.value.config.scopes;
        }
      }
    } else if (technicalType === "oidc") {
      config.client_id = form.value.config.client_id;
      config.client_secret = form.value.config.client_secret;
      if (
        form.value.provider_type === "microsoft" &&
        form.value.config.tenant_id
      ) {
        // Microsoft Entra: construct issuer URL from tenant ID
        const tenantId = form.value.config.tenant_id;
        config.issuer_url = `https://login.microsoftonline.com/${tenantId}/v2.0`;
      } else {
        config.issuer_url = form.value.config.issuer_url;
      }
      if (form.value.config.redirect_uri) {
        config.redirect_uri = form.value.config.redirect_uri;
      }
      if (form.value.config.scopes) {
        config.scopes = form.value.config.scopes;
      }
    }

    // Validate name uniqueness (frontend check for immediate feedback)
    const existingByName = providers.value.find(
      (p) =>
        p.name.toLowerCase() === form.value.name.toLowerCase() &&
        (!editingProvider.value || p.id !== editingProvider.value.id),
    );
    if (existingByName) {
      formError.value = `A provider with the name '${form.value.name}' already exists`;
      formLoading.value = false;
      return;
    }

    // Use preset instead of technical type
    if (!editingProvider.value) {
      const presetType = form.value.provider_type; // This is the preset (google, slack, etc.)
      const conflictingProvider = providers.value.find((p) => {
        if (!p.is_active) return false;
        // Get preset from provider config
        const pConfig = p.config || {};
        const pPreset =
          pConfig.provider_preset ||
          detectProviderPreset(p.provider_type, pConfig);
        return pPreset === presetType;
      });
      if (conflictingProvider) {
        formError.value = `Another ${presetType} provider ('${conflictingProvider.name}') is already active. Only one provider of each preset type can be active at a time.`;
        formLoading.value = false;
        return;
      }
    }

    // Store the original provider type for display, but use technical type for backend
    // Always store the preset in config, even if it's the same as technical type
    const presetType = form.value.provider_type; // This is the preset (google, slack, etc.)
    config.provider_preset = presetType;

    const providerData = {
      name: form.value.name,
      provider_type: technicalType,
      // is_active is managed via toggle, not in the form
      config: config,
    };

    if (editingProvider.value) {
      await admin.updateSSOProvider(editingProvider.value.id, providerData);
      formSuccess.value = "Provider updated successfully";
    } else {
      await admin.createSSOProvider(providerData);
      formSuccess.value = "Provider created successfully";
    }

    await loadProviders();
    setTimeout(() => {
      closeModal();
    }, 1500);
  } catch (err) {
    formError.value = err.message || "Failed to save provider";
    logger.error("Failed to save provider:", err);
  } finally {
    formLoading.value = false;
  }
};

const toggleProvider = async (provider) => {
  const newState = !provider.is_active;

  if (newState) {
    // Get preset from provider config
    const providerConfig = provider.config || {};
    const providerPreset =
      providerConfig.provider_preset ||
      detectProviderPreset(provider.provider_type, providerConfig);

    const conflictingProvider = providers.value.find((p) => {
      if (p.id === provider.id || !p.is_active) return false;
      // Get preset from other provider config
      const pConfig = p.config || {};
      const pPreset =
        pConfig.provider_preset ||
        detectProviderPreset(p.provider_type, pConfig);
      return pPreset === providerPreset;
    });
    if (conflictingProvider) {
      error.value = `Another ${providerPreset} provider ('${conflictingProvider.name}') is already active. Only one provider of each preset type can be active at a time.`;
      return;
    }
  }

  // Optimistically update the UI immediately
  const previousState = provider.is_active;
  provider.is_active = newState;

  try {
    await admin.updateSSOProvider(provider.id, {
      is_active: provider.is_active,
    });
    // Success - state already updated, no need to reload
    error.value = ""; // Clear any previous errors
  } catch (err) {
    // Revert on error
    provider.is_active = previousState;
    error.value = err.message || "Failed to update provider";
    logger.error("Failed to toggle provider:", err);
  }
};

const deleteProvider = (providerId) => {
  const provider = providers.value.find((p) => p.id === providerId);
  if (provider) {
    providerToDelete.value = provider;
    showDeleteModal.value = true;
  }
};

const closeDeleteModal = () => {
  showDeleteModal.value = false;
  providerToDelete.value = null;
};

const confirmDelete = async () => {
  if (!providerToDelete.value) return;

  deletingProvider.value = true;
  try {
    await admin.deleteSSOProvider(providerToDelete.value.id);
    await loadProviders();
    closeDeleteModal();
  } catch (err) {
    error.value = err.message || "Failed to delete provider";
    logger.error("Failed to delete provider:", err);
  } finally {
    deletingProvider.value = false;
  }
};

const formatDate = (dateString) => {
  if (!dateString) return "N/A";
  return new Date(dateString).toLocaleString();
};

const testSMTP = async () => {
  smtpTesting.value = true;
  smtpStatus.value = null;

  try {
    const result = await admin.testSMTP();
    smtpStatus.value = {
      success: result.success,
      message: result.message || "SMTP configuration is valid",
      error: result.error || null,
    };
  } catch (err) {
    smtpStatus.value = {
      success: false,
      message: null,
      error: err.message || "Failed to test SMTP configuration",
    };
  } finally {
    smtpTesting.value = false;
  }
};

// Test SMTP when email-magic-link provider type is selected
const onProviderTypeChange = () => {
  if (!form.value.provider_type || editingProvider.value) {
    return; // Don't override when editing
  }

  const defaults = getProviderDefaults(form.value.provider_type);
  const providerNames = {
    google: "Google",
    microsoft: "Microsoft Entra",
    slack: "Slack",
    discord: "Discord",
    gitlab: "GitLab",
    oidc: "OIDC Provider",
    "email-magic-link": "Email Magic Link",
    saml: "SAML Provider",
  };

  if (!form.value.name) {
    form.value.name = providerNames[form.value.provider_type] || "";
  }

  // Pre-fill defaults
  Object.keys(defaults).forEach((key) => {
    if (!form.value.config[key]) {
      form.value.config[key] = defaults[key];
    }
  });

  // Clear SMTP status when provider type changes (but don't test automatically)
  if (form.value.provider_type !== "email-magic-link") {
    smtpStatus.value = null;
  }
};

const handleSaveDomainRule = async () => {
  domainRuleForm.value.loading = true;
  domainRuleForm.value.error = null;
  domainRuleForm.value.success = null;

  if (!domainRuleForm.value.domain_pattern) {
    domainRuleForm.value.error = "Please enter a domain pattern";
    domainRuleForm.value.loading = false;
    return;
  }

  try {
    if (editingDomainRule.value) {
      await admin.updateDomainRule(editingDomainRule.value.id, {
        domain_pattern: domainRuleForm.value.domain_pattern,
      });
      domainRuleForm.value.success = "Domain rule updated successfully";
    } else {
      await admin.createDomainRule({
        domain_pattern: domainRuleForm.value.domain_pattern,
        is_active: true,
      });
      domainRuleForm.value.success = "Domain rule created successfully";
    }
    await loadDomainRules();
    setTimeout(() => {
      closeDomainRuleModal();
    }, 1500);
  } catch (err) {
    domainRuleForm.value.error = err.message || "Failed to save domain rule";
    logger.error("Failed to save domain rule:", err);
  } finally {
    domainRuleForm.value.loading = false;
  }
};

const editDomainRule = (rule) => {
  editingDomainRule.value = rule;
  domainRuleForm.value.domain_pattern = rule.domain_pattern;
  showDomainRuleModal.value = true;
};

const deleteDomainRule = (ruleId) => {
  showConfirm({
    title: "Delete Domain Rule",
    message: "Are you sure you want to delete this domain rule?",
    confirmText: "Delete",
    dangerous: true,
    onConfirm: async () => {
      try {
        await admin.deleteDomainRule(ruleId);
        await loadDomainRules();
        showAlert({
          type: "success",
          title: "Success",
          message: "Domain rule deleted successfully",
        });
      } catch (err) {
        showAlert({
          type: "error",
          title: "Error",
          message: err.message || "Failed to delete domain rule",
        });
        logger.error("Failed to delete domain rule:", err);
      }
    },
  });
};

const showAlert = (config) => {
  alertModalConfig.value = {
    type: config.type || "error",
    title: config.title || "Alert",
    message: config.message || "",
  };
  showAlertModal.value = true;
};

const showConfirm = (config) => {
  confirmModalConfig.value = {
    title: config.title || "Confirm Action",
    message: config.message || "Are you sure you want to proceed?",
    confirmText: config.confirmText || "Confirm",
    dangerous: config.dangerous || false,
    onConfirm: config.onConfirm || (() => {}),
  };
  showConfirmModal.value = true;
};

const handleConfirmModalConfirm = () => {
  if (confirmModalConfig.value.onConfirm) {
    confirmModalConfig.value.onConfirm();
  }
  showConfirmModal.value = false;
};

const handleConfirmModalCancel = () => {
  showConfirmModal.value = false;
};

const handleAlertModalClose = () => {
  showAlertModal.value = false;
};

const closeDomainRuleModal = () => {
  showDomainRuleModal.value = false;
  editingDomainRule.value = null;
  domainRuleForm.value.domain_pattern = "";
  domainRuleForm.value.error = null;
  domainRuleForm.value.success = null;
};

onMounted(() => {
  loadProviders();
  loadDomainRules();
  loadVaultUrl();
});
</script>

<style scoped>
.admin-sso-providers {
  max-width: 1200px;
  margin: 0 auto;
}

h1 {
  color: #a9b7aa;
  margin-bottom: 2rem;
}

.loading,
.error {
  padding: 1rem;

  margin-bottom: 1rem;
}

.error {
  background: rgba(239, 68, 68, 0.1);
  border: 1px solid rgba(239, 68, 68, 0.3) !important;
  color: #fca5a5;
}

.providers-section {
  background: var(--bg-modal);

  padding: 1.5rem;
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1.5rem;
}

.mobile-mode .section-header {
  flex-direction: column;
  align-items: flex-start;
  gap: 1rem;
  margin-bottom: 1rem;
}

.mobile-mode .section-header .btn {
  width: 100%;
}

.section-header h2 {
  color: #a9b7aa;
  margin: 0;
}

.empty-state {
  text-align: center;
  padding: 3rem;
  color: #a9b7aa;
}

.providers-list {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.mobile-mode .providers-list {
  gap: 0.75rem;
}

.provider-card {
  background: var(--bg-modal);
  border: 1px solid var(--border-color);

  padding: 1.5rem;
  width: 100%;
  box-sizing: border-box;
  overflow: hidden;
}

.mobile-mode .provider-card {
  padding: 1rem;
  max-width: 100%;
}

.provider-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1rem;
  gap: 0.75rem;
  flex-wrap: wrap;
}

.mobile-mode .provider-header {
  flex-direction: column;
  align-items: flex-start;
  gap: 0.75rem;
}

.provider-info {
  display: flex;
  align-items: center;
  gap: 1rem;
  flex: 1;
  min-width: 0;
}

.mobile-mode .provider-info {
  width: 100%;
  flex-wrap: wrap;
}

.provider-info h3 {
  color: #a9b7aa;
  margin: 0;
  word-break: break-word;
  overflow-wrap: break-word;
}

.mobile-mode .provider-info h3 {
  font-size: 0.95rem;
}

.provider-type {
  background: rgba(0, 66, 37, 0.2);
  color: var(--slate-grey);
  padding: 0.25rem 0.75rem;

  font-size: 0.75rem;
  font-weight: 600;
}

.provider-actions {
  display: flex;
  gap: 0.5rem;
  flex-shrink: 0;
}

.mobile-mode .provider-actions {
  width: 100%;
  justify-content: flex-start;
  flex-wrap: wrap;
  gap: 0.5rem;
}

.mobile-mode .provider-actions .btn {
  flex: 1 1 auto;
  min-width: 80px;
  font-size: 0.8rem;
  padding: 0.5rem 0.75rem;
}

.provider-details {
  color: #a9b7aa;
  font-size: 0.9rem;
  word-break: break-word;
  overflow-wrap: break-word;
}

.provider-details p {
  margin: 0.25rem 0;
  word-break: break-word;
  overflow-wrap: break-word;
}

.mobile-mode .provider-details {
  font-size: 0.8rem;
}

.mobile-mode .provider-details p {
  font-size: 0.8rem;
  line-height: 1.4;
}

.provider-inactive {
  opacity: 0.6;
  background: var(--bg-primary);
}

.toggle-container {
  display: flex;
  align-items: center;
}

.toggle-label {
  display: flex;
  align-items: center;
  cursor: pointer;
  user-select: none;
}

.toggle-switch {
  position: relative;
  width: 50px;
  height: 26px;
  background: rgba(0, 66, 37, 0.3);
  border: 1px solid var(--border-color);

  transition: all 0.3s ease;
  cursor: pointer;
}

.toggle-switch.active {
  background: var(--accent);
  border-color: var(--accent);
}

.toggle-slider {
  position: absolute;
  top: 2px;
  left: 2px;
  width: 20px;
  height: 20px;
  background: var(--text-primary);

  transition: all 0.3s ease;
}

.toggle-switch.active .toggle-slider {
  transform: translateX(24px);
  background: var(--text-primary);
}

/* Modal overlay uses global styles from vault.css with sidebar-specific padding */
.modal-overlay {
  padding: 1rem;
  background: var(--overlay-bg, rgba(0, 0, 0, 0.6));
  opacity: 1 !important;
  visibility: visible !important;
  animation: fadeIn 0.2s ease;
}

@keyframes fadeIn {
  from {
    opacity: 0;
  }
  to {
    opacity: 1;
  }
}

/* Modal uses global .modal styles from vault.css */
.modal-wide {
  width: 90%;
  overflow-y: visible;
}

.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 0;
  padding: 1.5rem 2rem;
  border-bottom: 1px solid #004225;
  flex-shrink: 0;
  position: relative;
  z-index: 10;
  width: 100%;
  box-sizing: border-box;
}

.modal-header h3 {
  margin: 0;
  color: #a9b7aa;
  font-size: 1.5rem;
  font-weight: 600;
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.modal-close-btn {
  background: transparent;
  border: 1px solid #004225;
  color: #a9b7aa;
  cursor: pointer;
  padding: 0.5rem;
  width: 36px;
  height: 36px;
  display: flex;
  align-items: center;
  justify-content: center;

  transition: all 0.2s ease;
  font-size: 1.5rem;
  line-height: 1;
}

.modal-close-btn:hover {
  background: #004225;
  color: #a9b7aa;
}

.modal-body {
  flex: 1;
  overflow-y: auto;
  min-height: 0;
  padding: 2rem;
  padding-top: 1.5rem;
  width: 100%;
  box-sizing: border-box;
}

.modal-form {
  width: 100%;
  display: flex;
  flex-direction: column;
  gap: 1.25rem;
}

.delete-modal .modal-body p {
  color: #a9b7aa;
  margin-bottom: 1rem;
  line-height: 1.6;
}

.delete-modal .modal-body strong {
  color: #fbbf24;
  font-weight: 600;
}

.delete-modal .warning-text {
  color: #f87171;
  font-size: 0.9rem;
  margin-top: 0.5rem;
}

.modal-footer {
  display: flex;
  justify-content: flex-end;
  gap: 1rem;
  padding: 1.5rem;
  border-top: 1px solid #004225;
}

.config-section {
  margin-top: 1.5rem;
  padding-top: 1.5rem;
  border-top: 1px solid #004225;
}

.config-section h3 {
  color: #a9b7aa;
  margin-bottom: 1rem;
  font-size: 1.1rem;
}

.config-description {
  color: #a9b7aa;
  font-size: 0.9rem;
  line-height: 1.5;
  margin-bottom: 1.5rem;
  padding: 1rem;
  background: var(--bg-primary);
  border: 1px solid var(--slate-grey);
  border-left: 3px solid var(--accent);
}

.config-description a {
  color: var(--slate-grey);
  text-decoration: none;
}

.config-description a:hover {
  text-decoration: underline;
}

.config-description code {
  background: var(--bg-primary);
  padding: 0.2rem 0.4rem;

  font-family: "Courier New", monospace;
  font-size: 0.85rem;
  color: var(--slate-grey);
  word-break: break-all;
}

.form-group {
  margin-bottom: 1.25rem;
}

.form-group label {
  display: block;
  color: #a9b7aa;
  margin-bottom: 0.5rem;
  font-weight: 500;
}

.form-group input[type="text"],
.form-group input[type="url"],
.form-group input[type="password"],
.form-group select,
.form-group textarea {
  width: 100%;
  padding: 0.75rem;
  background: var(--bg-primary);
  border: 1px solid var(--border-color);
  color: var(--slate-grey);
  font-size: 0.95rem;
}

.form-group input[type="checkbox"] {
  margin-right: 0.5rem;
}

.form-group small {
  display: block;
  color: #a9b7aa;
  font-size: 0.85rem;
  margin-top: 0.25rem;
}

.form-actions {
  display: flex;
  justify-content: flex-end;
  gap: 1rem;
  margin-top: 2rem;
  padding-top: 1.5rem;
  border-top: 1px solid #004225;
}

.btn {
  padding: 0.75rem 1.5rem;
  border: none;

  cursor: pointer;
  font-weight: 500;
  font-size: 0.95rem;
  transition: all 0.2s ease;
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
}

.btn-primary {
  background: transparent;
  color: var(--text-primary);
  border: 1px solid var(--accent);
}

.btn-primary:hover:not(:disabled) {
  background: rgba(0, 66, 37, 0.1);
  border-color: var(--accent);
}

.btn-secondary {
  background: #004225;
  color: #a9b7aa;
  border: 1px solid #004225;
}

.btn-secondary:hover:not(:disabled) {
  background: #004225;
}

.btn-danger {
  background: rgba(239, 68, 68, 0.2);
  color: #fca5a5;
  border: 1px solid rgba(239, 68, 68, 0.3) !important;
}

.btn-danger:hover:not(:disabled) {
  background: rgba(239, 68, 68, 0.3);
}

.btn-small {
  padding: 0.5rem 1rem;
  font-size: 0.85rem;
}

.btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.error-message {
  color: #fca5a5;
  padding: 0.75rem;
  background: rgba(239, 68, 68, 0.1);
  border: 1px solid rgba(239, 68, 68, 0.3) !important;

  margin-bottom: 1rem;
}

.success-message {
  color: #4ade80;
  padding: 0.75rem;
  background: rgba(34, 197, 94, 0.1);
  border: 1px solid rgba(34, 197, 94, 0.3);

  margin-bottom: 1rem;
}

.smtp-status {
  margin-bottom: 1.5rem;
  padding: 1rem;
  background: var(--bg-primary);

  border: 1px solid var(--border-color);
}

.smtp-status-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 0.75rem;
}

.smtp-status-label {
  color: #a9b7aa;
  font-weight: 500;
}

.smtp-status-message {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.75rem;

  font-size: 0.9rem;
}

.smtp-status-message.success {
  background: rgba(40, 167, 69, 0.1);
  border: 1px solid rgba(40, 167, 69, 0.3);
  color: #6cff8a;
}

.smtp-status-message.error {
  background: rgba(239, 68, 68, 0.1);
  border: 1px solid rgba(239, 68, 68, 0.3) !important;
  color: #fca5a5;
}

.smtp-status-icon {
  font-weight: bold;
  font-size: 1.1rem;
}

.smtp-status-text {
  flex: 1;
}

.password-auth-card {
  border: 2px solid var(--accent);
  background: rgba(0, 66, 37, 0.05);
}

.password-auth-card .provider-type {
  background: rgba(0, 66, 37, 0.2);
  color: var(--slate-grey);
}

.domain-rules-section {
  margin-top: 2rem;
  background: var(--bg-modal);

  padding: 1.5rem;
}

.button-group {
  display: flex;
  gap: 0.75rem;
}

@media (max-width: 768px) {
  .admin-sso-providers {
    padding: 0rem;
  }

  .button-group {
    flex-direction: column;
    width: 100%;
  }

  .button-group .btn {
    width: 100%;
  }
}

.domain-rules-list {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
  margin-top: 1rem;
}

.domain-rule-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 1rem;
  background: var(--bg-primary);
  border: 1px solid var(--border-color);

  transition: all 0.2s ease;
}

.domain-rule-item:hover {
  background: rgba(0, 66, 37, 0.1);
  border-color: var(--border-color);
}

.domain-rule-info {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  flex: 1;
}

.domain-rule-pattern {
  font-weight: 500;
  color: #a9b7aa;
  font-size: 1rem;
}

.domain-rule-status {
  font-size: 0.85rem;
  font-weight: 500;
  padding: 0.25rem 0.75rem;

  display: inline-block;
  width: fit-content;
}

.domain-rule-status.active {
  background: rgba(34, 197, 94, 0.2);
  color: #86efac;
  border: 1px solid rgba(34, 197, 94, 0.3);
}

.domain-rule-status.inactive {
  background: #004225;
  color: #a9b7aa;
  border: 1px solid #004225;
}

.domain-rule-actions {
  display: flex;
  gap: 0.5rem;
}
</style>
