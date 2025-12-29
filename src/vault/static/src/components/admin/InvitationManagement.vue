<template>
  <div class="invitation-management">
    <div class="section-header">
      <h2>Invitations</h2>
      <button @click="loadInvitations" class="btn btn-secondary">
        Refresh Invitations
      </button>
    </div>

    <div v-if="loading" class="loading">
      <span v-html="getIcon('clock', 24)"></span>
      Loading invitations...
    </div>
    <div v-else-if="error" class="error">{{ error }}</div>
    <div v-else class="invitations-container">
      <div v-if="invitations.length === 0" class="empty-state">
        <p>No pending invitations</p>
      </div>
      <div v-else class="invitations-list">
        <div
          v-for="invitation in invitations"
          :key="invitation.id"
          class="invitation-item"
        >
          <div class="invitation-info">
            <span class="invitation-email">{{ invitation.email }}</span>
            <span class="invitation-status" :class="getStatusClass(invitation)">
              {{ getStatus(invitation) }}
            </span>
            <span class="invitation-date">
              Created: {{ formatDate(invitation.created_at) }}
            </span>
          </div>
          <div class="invitation-actions">
            <button
              v-if="!invitation.accepted_at && !isExpired(invitation)"
              @click="resendInvitation(invitation.id)"
              class="btn btn-sm btn-secondary"
              :disabled="resending === invitation.id"
            >
              {{ resending === invitation.id ? "Resending..." : "Resend" }}
            </button>
            <button
              v-if="!invitation.accepted_at"
              @click="cancelInvitation(invitation.id)"
              class="btn btn-sm btn-danger"
              :disabled="cancelling === invitation.id"
            >
              {{ cancelling === invitation.id ? "Cancelling..." : "Cancel" }}
            </button>
          </div>
        </div>
      </div>
    </div>

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
</template>

<script>
import { ref, onMounted } from "vue";
import { admin } from "../../services/api";
import ConfirmationModal from "../ConfirmationModal.vue";
import AlertModal from "../AlertModal.vue";

export default {
  name: "InvitationManagement",
  components: {
    ConfirmationModal,
    AlertModal,
  },
  setup() {
    const invitations = ref([]);
    const loading = ref(false);
    const error = ref(null);
    const resending = ref(null);
    const cancelling = ref(null);
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

    const getIcon = (iconName, size = 24) => {
      try {
        if (!window || !window.Icons) {
          return "";
        }
        if (!window.Icons[iconName]) {
          return "";
        }
        const iconFn = window.Icons[iconName];
        if (typeof iconFn !== "function") {
          return "";
        }
        return iconFn.call(window.Icons, size, "currentColor");
      } catch (err) {
        return "";
      }
    };

    const loadInvitations = async () => {
      loading.value = true;
      error.value = null;
      try {
        const result = await admin.listInvitations({
          status: "pending",
          page: 1,
          per_page: 100,
        });
        invitations.value = result.invitations || [];
      } catch (err) {
        error.value = err.message || "Failed to load invitations";
        invitations.value = [];
      } finally {
        loading.value = false;
      }
    };

    const getStatus = (invitation) => {
      if (invitation.accepted_at) {
        return "Accepted";
      }
      if (isExpired(invitation)) {
        return "Expired";
      }
      return "Pending";
    };

    const isExpired = (invitation) => {
      if (!invitation.expires_at) {
        return false;
      }
      return new Date(invitation.expires_at) < new Date();
    };

    const getStatusClass = (invitation) => {
      if (invitation.accepted_at) {
        return "status-accepted";
      }
      if (isExpired(invitation)) {
        return "status-expired";
      }
      return "status-pending";
    };

    const resendInvitation = async (invitationId) => {
      resending.value = invitationId;
      try {
        await admin.resendInvitation(invitationId);
        showAlert({
          type: "success",
          title: "Success",
          message: "Invitation resent successfully",
        });
        await loadInvitations();
      } catch (err) {
        showAlert({
          type: "error",
          title: "Error",
          message: err.message || "Failed to resend invitation",
        });
      } finally {
        resending.value = null;
      }
    };

    const cancelInvitation = (invitationId) => {
      showConfirm({
        title: "Cancel Invitation",
        message: "Are you sure you want to cancel this invitation?",
        confirmText: "Cancel Invitation",
        dangerous: true,
        onConfirm: async () => {
          cancelling.value = invitationId;
          try {
            await admin.cancelInvitation(invitationId);
            await loadInvitations();
            showAlert({
              type: "success",
              title: "Success",
              message: "Invitation cancelled successfully",
            });
          } catch (err) {
            showAlert({
              type: "error",
              title: "Error",
              message: err.message || "Failed to cancel invitation",
            });
          } finally {
            cancelling.value = null;
          }
        },
      });
    };

    const formatDate = (dateString) => {
      if (!dateString) return "N/A";
      const date = new Date(dateString);
      return date.toLocaleString();
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

    onMounted(() => {
      loadInvitations();
    });

    return {
      invitations,
      loading,
      error,
      resending,
      cancelling,
      showConfirmModal,
      confirmModalConfig,
      showAlertModal,
      alertModalConfig,
      getIcon,
      loadInvitations,
      getStatus,
      isExpired,
      getStatusClass,
      resendInvitation,
      cancelInvitation,
      formatDate,
      showAlert,
      showConfirm,
      handleConfirmModalConfirm,
      handleConfirmModalCancel,
      handleAlertModalClose,
    };
  },
};
</script>

<style scoped>
.invitation-management {
  padding: 0;
  width: 100%;
  box-sizing: border-box;
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1.5rem;
  padding: 1.5rem;
}

.section-header h2 {
  margin: 0;
  color: #a9b7aa;
  font-size: 1.5rem;
  font-weight: 600;
}

.loading,
.error {
  padding: 2rem;
  text-align: center;
}

.loading {
  color: #a9b7aa;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.75rem;
}

.loading :deep(svg) {
  color: #004225;
  animation: spin 1s linear infinite;
}

@keyframes spin {
  from {
    transform: rotate(0deg);
  }
  to {
    transform: rotate(360deg);
  }
}

.error {
  color: #f87171;
  background: rgba(239, 68, 68, 0.1);
  border: 1px solid rgba(239, 68, 68, 0.3) !important;
}

.invitations-container {
  padding: 1.5rem;
}

.empty-state {
  text-align: center;
  padding: 2rem;
  color: #a9b7aa;
}

.invitations-list {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.invitation-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 1rem;
  border: 1px solid #004225;

  transition: all 0.2s ease;
}

.invitation-item:hover {
  background: var(--bg-modal);
  border-color: #004225;
}

.invitation-info {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  flex: 1;
}

.invitation-email {
  font-weight: 500;
  color: #a9b7aa;
  font-size: 1rem;
}

.invitation-status {
  font-size: 0.85rem;
  font-weight: 500;
  padding: 0.25rem 0.75rem;

  display: inline-block;
  width: fit-content;
}

.status-pending {
  background: rgba(251, 191, 36, 0.2);
  color: #fbbf24;
  border: 1px solid rgba(251, 191, 36, 0.3);
}

.status-accepted {
  background: rgba(34, 197, 94, 0.2);
  color: #86efac;
  border: 1px solid rgba(34, 197, 94, 0.3);
}

.status-expired {
  background: #004225;
  color: #a9b7aa;
  border: 1px solid #004225;
}

.invitation-date {
  font-size: 0.875rem;
  color: #a9b7aa;
}

.invitation-actions {
  display: flex;
  gap: 0.5rem;
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

.btn-secondary {
  background: #004225;
  color: #a9b7aa;
  border: 1px solid #004225;
}

.btn-secondary:hover:not(:disabled) {
  background: #004225;
  border-color: #004225;
}

.btn-danger {
  background: linear-gradient(
    135deg,
    rgba(239, 68, 68, 0.2) 0%,
    rgba(220, 38, 38, 0.2) 100%
  );
  color: #f87171;
  border: 1px solid rgba(239, 68, 68, 0.3) !important;
}

.btn-danger:hover:not(:disabled) {
  background: linear-gradient(
    135deg,
    rgba(239, 68, 68, 0.3) 0%,
    rgba(220, 38, 38, 0.3) 100%
  );
  border-color: #ef4444;
}

.btn-sm {
  padding: 0.5rem 1rem;
  font-size: 0.85rem;
}

.btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
  transform: none !important;
}

/* Glass morphism effect - uses global styles from assets/styles.css */
</style>
