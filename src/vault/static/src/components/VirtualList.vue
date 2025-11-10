<!-- Virtual scrolling list component for performance -->
<template>
  <div
    class="virtual-list"
    :style="{ height: containerHeight + 'px' }"
    ref="containerRef"
  >
    <div
      class="virtual-list-content"
      :style="{
        height: totalHeight + 'px',
        transform: `translateY(${offsetY}px)`,
      }"
    >
      <div
        v-for="(item, index) in visibleItems"
        :key="item.id || index"
        :style="{
          height: itemHeight + 'px',
          position: 'absolute',
          top: (startIndex + index) * itemHeight + 'px',
          width: '100%',
        }"
        class="virtual-list-item"
      >
        <slot :item="item" :index="startIndex + index" />
      </div>
    </div>
  </div>
</template>

<script>
import { ref, computed, onMounted, onUnmounted, watch } from "vue";
import { throttle } from "../utils/debounce";

export default {
  name: "VirtualList",
  props: {
    items: {
      type: Array,
      required: true,
    },
    itemHeight: {
      type: Number,
      default: 50,
    },
    containerHeight: {
      type: Number,
      default: 400,
    },
    overscan: {
      type: Number,
      default: 5, // Number of items to render outside visible area
    },
  },
  setup(props) {
    const containerRef = ref(null);
    const scrollTop = ref(0);

    const totalHeight = computed(() => props.items.length * props.itemHeight);

    const startIndex = computed(() => {
      const index = Math.floor(scrollTop.value / props.itemHeight);
      return Math.max(0, index - props.overscan);
    });

    const endIndex = computed(() => {
      const visibleCount = Math.ceil(props.containerHeight / props.itemHeight);
      const index = startIndex.value + visibleCount + props.overscan * 2;
      return Math.min(props.items.length, index);
    });

    const visibleItems = computed(() => {
      return props.items.slice(startIndex.value, endIndex.value);
    });

    const offsetY = computed(() => {
      return startIndex.value * props.itemHeight;
    });

    const handleScroll = throttle((event) => {
      if (containerRef.value) {
        scrollTop.value = containerRef.value.scrollTop;
      }
    }, 16); // ~60fps

    onMounted(() => {
      if (containerRef.value) {
        containerRef.value.addEventListener("scroll", handleScroll);
      }
    });

    onUnmounted(() => {
      if (containerRef.value) {
        containerRef.value.removeEventListener("scroll", handleScroll);
      }
    });

    watch(
      () => props.items,
      () => {
        // Reset scroll position when items change
        if (containerRef.value) {
          scrollTop.value = 0;
          containerRef.value.scrollTop = 0;
        }
      },
    );

    return {
      containerRef,
      scrollTop,
      totalHeight,
      startIndex,
      endIndex,
      visibleItems,
      offsetY,
    };
  },
};
</script>

<style scoped>
.virtual-list {
  overflow-y: auto;
  overflow-x: hidden;
  position: relative;
}

.virtual-list-content {
  position: relative;
}

.virtual-list-item {
  position: absolute;
  left: 0;
  right: 0;
}
</style>
