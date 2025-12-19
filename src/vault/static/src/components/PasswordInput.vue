<template>
  <div class="password-input-wrapper">
    <input
      :id="id"
      :type="showPassword ? 'text' : 'password'"
      :value="modelValue"
      @input="$emit('update:modelValue', $event.target.value)"
      @keyup="$emit('keyup', $event)"
      @keydown="$emit('keydown', $event)"
      :placeholder="placeholder"
      :required="required"
      :disabled="disabled"
      :autocomplete="autocomplete"
      :minlength="minlength"
      :maxlength="maxlength"
      :autofocus="autofocus"
      class="password-input"
    />
    <button
      type="button"
      class="password-toggle"
      :class="{ 'is-visible': showPassword }"
      :aria-label="showPassword ? 'Hide password' : 'Show password'"
      @click="togglePassword"
      :disabled="disabled"
    >
      <svg
        class="password-toggle-icon password-toggle-icon--hide"
        width="18"
        height="18"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        stroke-width="2"
        stroke-linecap="round"
        stroke-linejoin="round"
      >
        <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"></path>
        <path
          d="M8 12.5c0 .5.5 1.5 4 1.5s4-1 4-1.5"
          stroke-linecap="round"
        ></path>
      </svg>
      <svg
        class="password-toggle-icon password-toggle-icon--show"
        width="18"
        height="18"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        stroke-width="2"
        stroke-linecap="round"
        stroke-linejoin="round"
      >
        <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"></path>
        <circle cx="12" cy="12" r="3"></circle>
      </svg>
    </button>
  </div>
</template>

<script setup>
import { ref } from "vue";

const props = defineProps({
  modelValue: {
    type: String,
    default: "",
  },
  id: {
    type: String,
    default: "",
  },
  placeholder: {
    type: String,
    default: "",
  },
  required: {
    type: Boolean,
    default: false,
  },
  disabled: {
    type: Boolean,
    default: false,
  },
  autocomplete: {
    type: String,
    default: "current-password",
  },
  minlength: {
    type: [Number, String],
    default: undefined,
  },
  maxlength: {
    type: [Number, String],
    default: undefined,
  },
  autofocus: {
    type: Boolean,
    default: false,
  },
});

defineEmits(["update:modelValue", "keyup", "keydown"]);

const showPassword = ref(false);

const togglePassword = () => {
  showPassword.value = !showPassword.value;
};
</script>

<style scoped>
.password-input-wrapper {
  position: relative;
  display: block;
  width: 100%;
  /* Ensure wrapper maintains stable dimensions */
  min-height: fit-content;
}

/* Use :deep() to allow parent styles to apply to the input */
.password-input-wrapper :deep(.password-input) {
  padding-right: 2.5rem !important;
  width: 100%;
  box-sizing: border-box;
  /* Prevent input from changing size on hover/focus which could affect toggle position */
  min-height: inherit;
  height: auto;
  /* Apply form-input styles when used in modals */
  padding: 0.75rem 1rem;
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid #004225;

  color: var(--slate-grey);
  font-size: 0.95rem;
  font-family: inherit;
  transition: all 0.2s ease;
}

.password-input-wrapper :deep(.password-input):focus {
  outline: none;
  border-color: rgba(88, 166, 255, 0.5);
  background: rgba(255, 255, 255, 0.08);
  box-shadow: 0 0 0 3px rgba(88, 166, 255, 0.1);
}

.password-input-wrapper :deep(.password-input):disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.password-input-wrapper :deep(.password-input)::placeholder {
  color: var(--slate-grey);
}

.password-toggle {
  position: absolute;
  right: 0.5rem;
  top: 50%;
  margin-top: -12px;
  height: 24px;
  width: 24px;
  background: transparent;
  border: none;
  color: #a9b7aa;
  opacity: 0.7;
  cursor: pointer;
  padding: 0;
  margin-left: 0;
  margin-right: 0;
  margin-bottom: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  transition:
    opacity 0.2s ease,
    color 0.2s ease;
  z-index: 10;
  /* Explicitly prevent transform from being affected - use margin-top instead */
  transition-property: opacity, color;
  /* Prevent any layout shifts */
  box-sizing: border-box;
  line-height: 1;
  /* Prevent button from being affected by parent styles */
  vertical-align: baseline;
}

.password-toggle:hover:not(:disabled) {
  opacity: 1;
  color: #a9b7aa;
  /* Maintain exact same position on hover */
  margin-top: -12px;
}

.password-toggle:active:not(:disabled) {
  opacity: 0.8;
  /* Maintain exact same position on active */
  margin-top: -12px;
}

.password-toggle:focus {
  outline: none;
  /* Maintain exact same position on focus */
  margin-top: -12px;
}

.password-toggle:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.password-toggle-icon {
  display: block;
  width: 18px;
  height: 18px;
}

.password-toggle-icon--show {
  display: none;
}

.password-toggle.is-visible .password-toggle-icon--hide {
  display: none;
}

.password-toggle.is-visible .password-toggle-icon--show {
  display: block;
}
</style>
