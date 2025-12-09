<template>
  <div
    class="custom-select"
    :class="{
      'is-open': isOpen,
      'is-disabled': disabled,
      'is-placeholder': isPlaceholder,
    }"
    ref="selectContainer"
  >
    <button
      type="button"
      class="custom-select-trigger"
      :class="triggerClass"
      @click.stop="toggleDropdown"
      @keydown.enter.prevent="toggleDropdown"
      @keydown.space.prevent="toggleDropdown"
      @keydown.escape="closeDropdown"
      @keydown.down.prevent="openDropdown"
      @keydown.up.prevent="openDropdown"
      :disabled="disabled"
      :aria-expanded="isOpen"
      :aria-haspopup="true"
      :aria-label="label"
    >
      <span class="custom-select-value">{{ displayValue || placeholder }}</span>
      <span class="custom-select-arrow" :class="{ 'is-open': isOpen }">
        <span v-html="getIcon('chevron-down')"></span>
      </span>
    </button>
    <teleport to="body">
      <transition name="dropdown-fade">
        <div
          v-if="isOpen"
          class="custom-select-dropdown-container"
          :style="dropdownStyle"
          ref="dropdownContainer"
          @click.stop
        >
          <div class="custom-select-dropdown" ref="dropdown">
            <div class="custom-select-options">
              <button
                v-for="option in options"
                :key="getOptionValue(option)"
                type="button"
                class="custom-select-option"
                :class="{ 'is-selected': isSelected(option) }"
                @click="selectOption(option)"
                @mouseenter="handleOptionMouseEnter(option)"
              >
                <span class="custom-select-option-text">{{
                  getOptionLabel(option)
                }}</span>
                <span
                  v-if="isSelected(option)"
                  class="custom-select-option-check"
                >
                  <span v-html="getIcon('check')"></span>
                </span>
              </button>
            </div>
          </div>
        </div>
      </transition>
    </teleport>
  </div>
</template>

<script>
import { ref, computed, watch, nextTick, onMounted, onUnmounted } from "vue";
export default {
  name: "CustomSelect",
  components: {},
  props: {
    modelValue: {
      type: [String, Number],
      default: null,
    },
    options: {
      type: Array,
      required: true,
    },
    optionLabel: {
      type: String,
      default: "label",
    },
    optionValue: {
      type: String,
      default: "value",
    },
    placeholder: {
      type: String,
      default: "Select an option",
    },
    disabled: {
      type: Boolean,
      default: false,
    },
    label: {
      type: String,
      default: "",
    },
    size: {
      type: String,
      default: "medium",
      validator: (value) => ["small", "medium", "large"].includes(value),
    },
  },
  emits: ["update:modelValue", "change"],
  setup(props, { emit }) {
    const isOpen = ref(false);
    const selectContainer = ref(null);
    const dropdown = ref(null);
    const dropdownContainer = ref(null);
    const highlightedIndex = ref(-1);
    const clickOutsideHandler = ref(null);
    const escapeKeyHandler = ref(null);
    const resizeHandler = ref(null);
    const scrollHandler = ref(null);
    const dropdownTop = ref(0);
    const dropdownLeft = ref(0);
    const dropdownWidth = ref(0);

    const displayValue = computed(() => {
      if (
        props.modelValue === null ||
        props.modelValue === undefined ||
        props.modelValue === ""
      ) {
        return props.placeholder;
      }
      const selectedOption = props.options.find(
        (opt) => getOptionValue(opt) === props.modelValue,
      );
      return selectedOption
        ? getOptionLabel(selectedOption)
        : props.placeholder;
    });

    const triggerClass = computed(() => {
      return {
        "custom-select-trigger-sm": props.size === "small",
        "custom-select-trigger-lg": props.size === "large",
      };
    });

    const isPlaceholder = computed(() => {
      return (
        props.modelValue === null ||
        props.modelValue === undefined ||
        props.modelValue === ""
      );
    });

    const dropdownStyle = computed(() => {
      return {
        position: "fixed",
        top: `${dropdownTop.value}px`,
        left: `${dropdownLeft.value}px`,
        width: `${dropdownWidth.value}px`,
        zIndex: 100001,
      };
    });

    const getOptionLabel = (option) => {
      if (typeof option === "string") return option;
      return option[props.optionLabel] || option.label || option;
    };

    const getOptionValue = (option) => {
      if (typeof option === "string") return option;
      return option[props.optionValue] || option.value || option;
    };

    const isSelected = (option) => {
      return getOptionValue(option) === props.modelValue;
    };

    const getIcon = (iconName) => {
      if (!window.Icons) return "";
      if (window.Icons[iconName]) {
        return window.Icons[iconName](16, "currentColor");
      }
      return "";
    };

    const calculateDropdownWidth = () => {
      if (!selectContainer.value) return 0;

      const triggerRect = selectContainer.value
        .querySelector(".custom-select-trigger")
        ?.getBoundingClientRect();
      if (!triggerRect) return 0;

      // Create a measurement element for text with the same styles
      const textMeasure = document.createElement("span");
      textMeasure.style.position = "absolute";
      textMeasure.style.visibility = "hidden";
      textMeasure.style.top = "-9999px";
      textMeasure.style.left = "-9999px";
      textMeasure.style.whiteSpace = "nowrap";
      textMeasure.style.padding = "0";
      textMeasure.style.margin = "0";
      textMeasure.style.border = "none";

      const triggerElement = selectContainer.value.querySelector(
        ".custom-select-trigger",
      );
      const triggerStyle = window.getComputedStyle(triggerElement);
      textMeasure.style.fontSize = triggerStyle.fontSize;
      textMeasure.style.fontFamily = triggerStyle.fontFamily;
      textMeasure.style.fontWeight = triggerStyle.fontWeight;
      textMeasure.style.letterSpacing = triggerStyle.letterSpacing;
      document.body.appendChild(textMeasure);

      // Find the maximum text width among all options
      let maxTextWidth = 0;
      props.options.forEach((option) => {
        textMeasure.textContent = getOptionLabel(option);
        const width = textMeasure.offsetWidth;
        if (width > maxTextWidth) {
          maxTextWidth = width;
        }
      });

      document.body.removeChild(textMeasure);

      // Create a measurement element for a complete option (with padding and icon)
      const optionMeasure = document.createElement("div");
      optionMeasure.style.position = "absolute";
      optionMeasure.style.visibility = "hidden";
      optionMeasure.style.top = "-9999px";
      optionMeasure.style.left = "-9999px";
      optionMeasure.style.display = "inline-flex";
      optionMeasure.style.alignItems = "center";
      optionMeasure.style.whiteSpace = "nowrap";

      // Get actual CSS values from styles
      // We'll create a temporary option element in the DOM to get its styles
      const tempOption = document.createElement("button");
      tempOption.className = "custom-select-option";
      tempOption.style.position = "absolute";
      tempOption.style.visibility = "hidden";
      tempOption.style.top = "-9999px";
      tempOption.style.left = "-9999px";
      document.body.appendChild(tempOption);

      // Wait for styles to be applied
      const optionStyle = window.getComputedStyle(tempOption);
      const optionPaddingLeft = parseFloat(optionStyle.paddingLeft) || 12;
      const optionPaddingRight = parseFloat(optionStyle.paddingRight) || 12;
      const optionGap = parseFloat(optionStyle.gap) || 8;

      document.body.removeChild(tempOption);

      // Check icon width (16px) + gap
      const checkIconWidth = 16 + optionGap;

      // Get dropdown container padding
      const tempContainer = document.createElement("div");
      tempContainer.className = "custom-select-dropdown";
      tempContainer.style.position = "absolute";
      tempContainer.style.visibility = "hidden";
      tempContainer.style.top = "-9999px";
      tempContainer.style.left = "-9999px";
      document.body.appendChild(tempContainer);

      const containerStyle = window.getComputedStyle(tempContainer);
      const containerPaddingLeft = parseFloat(containerStyle.paddingLeft) || 4;
      const containerPaddingRight =
        parseFloat(containerStyle.paddingRight) || 4;

      document.body.removeChild(tempContainer);

      // Calculate total required width
      // Add a bit more margin to ensure all text is visible
      const totalPadding =
        containerPaddingLeft +
        containerPaddingRight +
        optionPaddingLeft +
        optionPaddingRight +
        checkIconWidth;
      const calculatedWidth = maxTextWidth + totalPadding;

      // Minimum width is that of the trigger button
      const minWidth = triggerRect.width;
      const finalWidth = Math.max(minWidth, calculatedWidth);

      // Add a generous safety margin to avoid rounding and rendering issues
      // We add 16px margin (8px on each side) to be sure
      return Math.ceil(finalWidth) + 16;
    };

    const calculateDropdownPosition = () => {
      if (!selectContainer.value) return;

      const triggerRect = selectContainer.value
        .querySelector(".custom-select-trigger")
        ?.getBoundingClientRect();
      if (!triggerRect) return;

      // Calculate optimal width based on content
      dropdownWidth.value = calculateDropdownWidth();
      dropdownLeft.value = triggerRect.left;
      dropdownTop.value = triggerRect.bottom + 4; // 0.25rem = 4px

      // Adjust if menu exceeds window
      nextTick(() => {
        if (dropdownContainer.value && dropdown.value) {
          const dropdownRect = dropdown.value.getBoundingClientRect();
          const viewportWidth = window.innerWidth;
          const viewportHeight = window.innerHeight;

          // Adjust horizontally
          if (dropdownRect.right > viewportWidth - 10) {
            dropdownLeft.value = viewportWidth - dropdownRect.width - 10;
          }
          if (dropdownLeft.value < 10) {
            dropdownLeft.value = 10;
          }

          // Adjust vertically (open upward if necessary)
          if (dropdownRect.bottom > viewportHeight - 10) {
            const spaceAbove = triggerRect.top;
            const spaceBelow = viewportHeight - triggerRect.bottom;
            if (spaceAbove > spaceBelow && spaceAbove > dropdownRect.height) {
              dropdownTop.value = triggerRect.top - dropdownRect.height - 4;
            } else {
              dropdownTop.value = viewportHeight - dropdownRect.height - 10;
            }
          }
          if (dropdownTop.value < 10) {
            dropdownTop.value = 10;
          }
        }
      });
    };

    const toggleDropdown = () => {
      if (props.disabled) return;
      isOpen.value = !isOpen.value;
      if (isOpen.value) {
        calculateDropdownPosition();
        nextTick(() => {
          setupClickOutside();
          setupKeyboardNavigation();
          setupPositionListeners();
        });
      } else {
        removePositionListeners();
      }
    };

    const openDropdown = () => {
      if (props.disabled) return;
      if (!isOpen.value) {
        isOpen.value = true;
        calculateDropdownPosition();
        nextTick(() => {
          setupClickOutside();
          setupKeyboardNavigation();
          setupPositionListeners();
        });
      }
    };

    const closeDropdown = () => {
      isOpen.value = false;
      highlightedIndex.value = -1;
      removeEventListeners();
      removePositionListeners();
    };

    const setupPositionListeners = () => {
      resizeHandler.value = () => {
        if (isOpen.value) {
          calculateDropdownPosition();
        }
      };
      scrollHandler.value = () => {
        if (isOpen.value) {
          calculateDropdownPosition();
        }
      };
      window.addEventListener("resize", resizeHandler.value);
      window.addEventListener("scroll", scrollHandler.value, true);
    };

    const removePositionListeners = () => {
      if (resizeHandler.value) {
        window.removeEventListener("resize", resizeHandler.value);
        resizeHandler.value = null;
      }
      if (scrollHandler.value) {
        window.removeEventListener("scroll", scrollHandler.value, true);
        scrollHandler.value = null;
      }
    };

    const handleOptionMouseEnter = (option) => {
      highlightedIndex.value = props.options.indexOf(option);
    };

    const selectOption = (option) => {
      const value = getOptionValue(option);
      emit("update:modelValue", value);
      emit("change", value);
      closeDropdown();
    };

    const setupClickOutside = () => {
      clickOutsideHandler.value = (e) => {
        if (
          selectContainer.value &&
          !selectContainer.value.contains(e.target) &&
          dropdownContainer.value &&
          !dropdownContainer.value.contains(e.target)
        ) {
          closeDropdown();
        }
      };
      document.addEventListener("click", clickOutsideHandler.value);
    };

    const setupKeyboardNavigation = () => {
      escapeKeyHandler.value = (e) => {
        if (e.key === "Escape" && isOpen.value) {
          closeDropdown();
          if (selectContainer.value) {
            const trigger = selectContainer.value.querySelector(
              ".custom-select-trigger",
            );
            if (trigger) trigger.focus();
          }
        }
      };
      document.addEventListener("keydown", escapeKeyHandler.value);
    };

    const removeEventListeners = () => {
      if (clickOutsideHandler.value) {
        document.removeEventListener("click", clickOutsideHandler.value);
        clickOutsideHandler.value = null;
      }
      if (escapeKeyHandler.value) {
        document.removeEventListener("keydown", escapeKeyHandler.value);
        escapeKeyHandler.value = null;
      }
    };

    watch(
      () => props.modelValue,
      () => {
        highlightedIndex.value = props.options.findIndex(
          (opt) => getOptionValue(opt) === props.modelValue,
        );
      },
    );

    onMounted(() => {
      // Set initial highlighted index
      if (props.modelValue) {
        highlightedIndex.value = props.options.findIndex(
          (opt) => getOptionValue(opt) === props.modelValue,
        );
      }
    });

    onUnmounted(() => {
      removeEventListeners();
      removePositionListeners();
    });

    return {
      options: computed(() => props.options),
      isOpen,
      selectContainer,
      dropdown,
      dropdownContainer,
      highlightedIndex,
      displayValue,
      triggerClass,
      isPlaceholder,
      dropdownStyle,
      toggleDropdown,
      openDropdown,
      closeDropdown,
      handleOptionMouseEnter,
      selectOption,
      getOptionLabel,
      getOptionValue,
      isSelected,
      getIcon,
    };
  },
};
</script>

<style scoped>
.custom-select {
  position: relative;
  width: 100%;
}

.custom-select-trigger {
  width: 100%;
  padding: 0.75rem 1rem;
  padding-right: 2.5rem;
  background: rgba(30, 41, 59, 0.4);
  backdrop-filter: blur(20px) saturate(180%);
  -webkit-backdrop-filter: blur(20px) saturate(180%);
  border: 1px solid rgba(148, 163, 184, 0.2);
  border-radius: 0.75rem;
  color: #e6eef6;
  font-size: 0.95rem;
  font-family:
    -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue",
    Arial, sans-serif;
  cursor: pointer;
  transition: all 0.2s ease;
  display: flex;
  align-items: center;
  justify-content: space-between;
  text-align: left;
  min-height: 2.5rem;
  position: relative;
  box-sizing: border-box;
}

.custom-select-trigger:hover:not(:disabled) {
  border-color: var(--border-color-hover);
  background: var(--bg-glass-hover);
}

.custom-select-trigger:focus {
  outline: none;
  border-color: var(--accent-blue);
  background: var(--bg-glass-hover);
  box-shadow: 0 0 0 3px rgba(56, 189, 248, 0.1);
}

.custom-select-trigger:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.custom-select-trigger-sm {
  padding: 0.5rem;
  padding-right: 1.75rem;
  font-size: 0.85rem;
  min-height: 2rem;
}

.custom-select-trigger-sm .custom-select-arrow {
  right: 0.5rem;
}

.custom-select-trigger-lg {
  padding: var(--space-4) var(--space-5);
  padding-right: 3rem;
  font-size: var(--font-size-lg);
  min-height: 3rem;
}

.custom-select-value {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: #e6eef6;
  padding-right: 0.5rem;
  min-height: 1.2em;
  line-height: 1.5;
  display: block;
}

.custom-select.is-placeholder .custom-select-value {
  color: #94a3b8;
}

.custom-select-arrow {
  position: absolute;
  right: 0.75rem;
  top: 50%;
  transform: translateY(-50%);
  display: flex;
  align-items: center;
  justify-content: center;
  transition: transform 0.2s ease;
  color: #94a3b8;
  flex-shrink: 0;
  width: 1rem;
  height: 1rem;
  pointer-events: none;
}

.custom-select-arrow.is-open {
  transform: translateY(-50%) rotate(180deg);
}

.custom-select-arrow svg {
  width: 16px;
  height: 16px;
}

.custom-select-dropdown-container {
  position: fixed;
  z-index: 100001;
  pointer-events: none;
}

.custom-select-dropdown-container * {
  pointer-events: auto;
}

.custom-select-dropdown {
  width: 100%;
  background: rgba(30, 41, 59, 0.85);
  backdrop-filter: blur(20px) saturate(180%);
  -webkit-backdrop-filter: blur(20px) saturate(180%);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-lg);
  overflow: hidden;
  max-height: 300px;
  overflow-y: auto;
}

.custom-select-options {
  display: flex;
  flex-direction: column;
  padding: 0.25rem;
}

.custom-select-option {
  width: 100%;
  padding: var(--space-2) var(--space-3);
  background: transparent;
  border: none;
  border-radius: var(--radius-sm);
  color: var(--text-primary);
  font-size: var(--font-size-base);
  font-family: var(--font-family-base);
  text-align: left;
  cursor: pointer;
  transition: all var(--transition-base);
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-2);
}

.custom-select-option:hover {
  background: rgba(30, 41, 59, 0.6);
}

.custom-select-option.is-selected {
  background: rgba(56, 189, 248, 0.1);
  color: #38bdf8;
}

.custom-select-option-text {
  white-space: nowrap;
  flex-shrink: 0;
}

.custom-select-option-check {
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--accent-blue);
  flex-shrink: 0;
}

.custom-select-option-check svg {
  width: 16px;
  height: 16px;
}

/* Transitions */
.dropdown-fade-enter-active,
.dropdown-fade-leave-active {
  transition:
    opacity var(--transition-base),
    transform var(--transition-base);
}

.dropdown-fade-enter-from,
.dropdown-fade-leave-to {
  opacity: 0;
  transform: translateY(-0.5rem);
}

.custom-select.is-disabled .custom-select-trigger {
  opacity: 0.5;
  cursor: not-allowed;
}
</style>
