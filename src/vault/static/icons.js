/** @file icons.js - SVG icon system for Leyzen Vault */

// SVG Icons system - Professional, minimal icons
window.Icons = {
  // Helper to create SVG with size and color
  createSVG: function (
    path,
    size = 24,
    color = "currentColor",
    useFill = false,
  ) {
    const fillAttr = useFill ? `fill="${color}"` : `fill="none"`;
    const strokeAttr = useFill ? `stroke="none"` : `stroke="${color}"`;
    return `<svg width="${size}" height="${size}" viewBox="0 0 24 24" ${fillAttr} ${strokeAttr} stroke-width="2" stroke-linecap="round" stroke-linejoin="round">${path}</svg>`;
  },

  // Folder icon
  folder: function (size, color) {
    return this.createSVG(
      '<path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"></path>',
      size,
      color,
    );
  },

  // File/document icon
  file: function (size, color) {
    return this.createSVG(
      '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline>',
      size,
      color,
    );
  },

  // Delete/trash icon
  delete: function (size, color) {
    return this.createSVG(
      '<polyline points="3 6 5 6 21 6"></polyline><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path><line x1="10" y1="11" x2="10" y2="17"></line><line x1="14" y1="11" x2="14" y2="17"></line>',
      size,
      color,
    );
  },

  // Star icon
  star: function (size, color) {
    return this.createSVG(
      '<polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"></polygon>',
      size,
      color,
    );
  },

  // Users/group icon
  users: function (size, color) {
    return this.createSVG(
      '<path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"></path><circle cx="9" cy="7" r="4"></circle><path d="M23 21v-2a4 4 0 0 0-3-3.87"></path><path d="M16 3.13a4 4 0 0 1 0 7.75"></path>',
      size,
      color,
    );
  },

  // Clock/recent icon
  clock: function (size, color) {
    return this.createSVG(
      '<circle cx="12" cy="12" r="10"></circle><polyline points="12 6 12 12 16 14"></polyline>',
      size,
      color,
    );
  },

  // Lock icon
  lock: function (size, color) {
    return this.createSVG(
      '<rect x="3" y="11" width="18" height="11" rx="2" ry="2"></rect><path d="M7 11V7a5 5 0 0 1 10 0v4"></path>',
      size,
      color,
    );
  },

  // Key icon
  key: function (size, color) {
    return this.createSVG(
      '<path d="M21 2l-2 2m-7.61 7.61a5.5 5.5 0 1 1-7.778 7.778 5.5 5.5 0 0 1 7.777-7.777zm0 0L15.5 7.5m0 0l3 3L22 7l-3-3m-3.5 3.5L19 4"></path>',
      size,
      color,
    );
  },

  // User icon
  user: function (size, color) {
    return this.createSVG(
      '<path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"></path><circle cx="12" cy="7" r="4"></circle>',
      size,
      color,
    );
  },

  // Settings icon
  settings: function (size, color) {
    return this.createSVG(
      '<circle cx="12" cy="12" r="3"></circle><path d="M12 1v6m0 6v6m9-9h-6m-6 0H1m15.364 6.364l-4.243-4.243m-4.242 0L6.636 17.364m10.728 0l-4.243-4.243m-4.242 0L6.636 6.636"></path>',
      size,
      color,
    );
  },

  // Logout icon
  logout: function (size, color) {
    return this.createSVG(
      '<path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"></path><polyline points="16 17 21 12 16 7"></polyline><line x1="21" y1="12" x2="9" y2="12"></line>',
      size,
      color,
    );
  },

  // Upload icon
  upload: function (size, color) {
    return this.createSVG(
      '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path><polyline points="17 8 12 3 7 8"></polyline><line x1="12" y1="3" x2="12" y2="15"></line>',
      size,
      color,
    );
  },

  // Download icon
  download: function (size, color) {
    return this.createSVG(
      '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path><polyline points="7 10 12 15 17 10"></polyline><line x1="12" y1="15" x2="12" y2="3"></line>',
      size,
      color,
    );
  },

  // Link/share icon
  link: function (size, color) {
    return this.createSVG(
      '<path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"></path><path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"></path>',
      size,
      color,
    );
  },

  // Eye/preview icon
  eye: function (size, color) {
    return this.createSVG(
      '<path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"></path><circle cx="12" cy="12" r="3"></circle>',
      size,
      color,
    );
  },

  // Mail/envelope icon
  mail: function (size, color) {
    return this.createSVG(
      '<rect x="2" y="4" width="20" height="16" rx="2" ry="2"></rect><polyline points="22 6 12 13 2 6"></polyline>',
      size,
      color,
    );
  },

  // Edit icon
  edit: function (size, color) {
    return this.createSVG(
      '<path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"></path><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"></path>',
      size,
      color,
    );
  },

  // Copy/clipboard icon
  clipboard: function (size, color) {
    return this.createSVG(
      '<path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2"></path><rect x="8" y="2" width="8" height="4" rx="1" ry="1"></rect>',
      size,
      color,
    );
  },

  // Copy icon
  copy: function (size, color) {
    return this.createSVG(
      '<rect x="9" y="9" width="13" height="13" rx="2" ry="2" fill="none"></rect><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path>',
      size,
      color,
    );
  },

  // Move icon (arrows)
  move: function (size, color) {
    return this.createSVG(
      '<polyline points="5 9 2 12 5 15"></polyline><polyline points="9 5 12 2 15 5"></polyline><polyline points="15 19 12 22 9 19"></polyline><polyline points="19 9 22 12 19 15"></polyline><line x1="2" y1="12" x2="22" y2="12"></line><line x1="12" y1="2" x2="12" y2="22"></line>',
      size,
      color,
    );
  },

  // Search icon
  search: function (size, color) {
    return this.createSVG(
      '<circle cx="11" cy="11" r="8"></circle><path d="m21 21-4.35-4.35"></path>',
      size,
      color,
    );
  },

  // Plus/add icon
  plus: function (size, color) {
    return this.createSVG(
      '<line x1="12" y1="5" x2="12" y2="19"></line><line x1="5" y1="12" x2="19" y2="12"></line>',
      size,
      color,
    );
  },

  // Chart icon
  chart: function (size, color) {
    return this.createSVG(
      '<line x1="18" y1="20" x2="18" y2="10"></line><line x1="12" y1="20" x2="12" y2="4"></line><line x1="6" y1="20" x2="6" y2="14"></line>',
      size,
      color,
    );
  },

  // Moon/dark icon
  moon: function (size, color) {
    return this.createSVG(
      '<path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"></path>',
      size,
      color,
    );
  },

  // Sun/light icon
  sun: function (size, color) {
    return this.createSVG(
      '<circle cx="12" cy="12" r="5"></circle><line x1="12" y1="1" x2="12" y2="3"></line><line x1="12" y1="21" x2="12" y2="23"></line><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"></line><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"></line><line x1="1" y1="12" x2="3" y2="12"></line><line x1="21" y1="12" x2="23" y2="12"></line><line x1="4.22" y1="19.78" x2="5.64" y2="18.36"></line><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"></line>',
      size,
      color,
    );
  },

  // Warning icon
  warning: function (size, color) {
    return this.createSVG(
      '<path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"></path><line x1="12" y1="9" x2="12" y2="13"></line><line x1="12" y1="17" x2="12.01" y2="17"></line>',
      size,
      color,
    );
  },

  // More/3 dots icon (vertical)
  moreVertical: function (size, color) {
    return this.createSVG(
      '<circle cx="12" cy="5" r="2"></circle><circle cx="12" cy="12" r="2"></circle><circle cx="12" cy="19" r="2"></circle>',
      size,
      color,
      true, // use fill for circles
    );
  },

  // Grid view icon
  grid: function (size, color) {
    return this.createSVG(
      '<rect x="3" y="3" width="7" height="7"></rect><rect x="14" y="3" width="7" height="7"></rect><rect x="14" y="14" width="7" height="7"></rect><rect x="3" y="14" width="7" height="7"></rect>',
      size,
      color,
    );
  },

  // List view icon
  list: function (size, color) {
    return this.createSVG(
      '<line x1="8" y1="6" x2="21" y2="6"></line><line x1="8" y1="12" x2="21" y2="12"></line><line x1="8" y1="18" x2="21" y2="18"></line><line x1="3" y1="6" x2="3.01" y2="6"></line><line x1="3" y1="12" x2="3.01" y2="12"></line><line x1="3" y1="18" x2="3.01" y2="18"></line>',
      size,
      color,
    );
  },

  // Home icon
  home: function (size, color) {
    return this.createSVG(
      '<path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"></path><polyline points="9 22 9 12 15 12 15 22"></polyline>',
      size,
      color,
    );
  },

  // Image icon
  image: function (size, color) {
    return this.createSVG(
      '<rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect><circle cx="8.5" cy="8.5" r="1.5"></circle><polyline points="21 15 16 10 5 21"></polyline>',
      size,
      color,
    );
  },

  // Chevron down icon
  chevronDown: function (size, color) {
    return this.createSVG(
      '<polyline points="6 9 12 15 18 9"></polyline>',
      size,
      color,
    );
  },

  // Chevron down (alias)
  "chevron-down": function (size, color) {
    return this.chevronDown(size, color);
  },

  // Check icon
  check: function (size, color) {
    return this.createSVG(
      '<polyline points="20 6 9 17 4 12"></polyline>',
      size,
      color,
    );
  },

  // Trash icon (alias for delete, but can be used for trash/delete)
  trash: function (size, color) {
    return this.delete(size, color);
  },

  // Restore/rotate counter-clockwise icon
  restore: function (size, color) {
    return this.createSVG(
      '<polyline points="1 4 1 10 7 10"></polyline><path d="M3.51 15a9 9 0 1 0 2.13-9.36L1 10"></path>',
      size,
      color,
    );
  },

  // Success icon (checkmark in circle)
  success: function (size, color) {
    return this.createSVG(
      '<circle cx="12" cy="12" r="10"></circle><polyline points="9 12 11 14 15 10"></polyline>',
      size,
      color,
    );
  },

  // Error icon (X in circle)
  error: function (size, color) {
    return this.createSVG(
      '<circle cx="12" cy="12" r="10"></circle><line x1="15" y1="9" x2="9" y2="15"></line><line x1="9" y1="9" x2="15" y2="15"></line>',
      size,
      color,
    );
  },

  // Info icon (i in circle)
  info: function (size, color) {
    return this.createSVG(
      '<circle cx="12" cy="12" r="10"></circle><line x1="12" y1="16" x2="12" y2="12"></line><line x1="12" y1="8" x2="12.01" y2="8"></line>',
      size,
      color,
    );
  },

  // Sparkles icon (multiple sparkles/stars)
  sparkles: function (size, color) {
    // Sparkles arrangement: top-right (medium), center-left (large), bottom-right (small)
    const fillAttr = `fill="none"`;
    const strokeAttr = `stroke="${color}"`;
    return `<svg width="${size}" height="${size}" viewBox="0 0 32 32" ${fillAttr} ${strokeAttr} stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M28,8a1,1,0,0,1-1,1,4,4,0,0,0-4,4,1,1,0,0,1-2,0,4,4,0,0,0-4-4,1,1,0,0,1,0-2,4,4,0,0,0,4-4,1,1,0,0,1,2,0,4,4,0,0,0,4,4A1,1,0,0,1,28,8Z"></path><path d="M14,16a1,1,0,0,1-1,1,5,5,0,0,0-5,5,1,1,0,0,1-2,0,5,5,0,0,0-5-5,1,1,0,0,1,0-2,5,5,0,0,0,5-5,1,1,0,0,1,2,0,5,5,0,0,0,5,5A1,1,0,0,1,14,16Z"></path><path d="M24,24a1,1,0,0,1-1,1,2,2,0,0,0-2,2,1,1,0,0,1-2,0,2,2,0,0,0-2-2,1,1,0,0,1,0-2,2,2,0,0,0,2-2,1,1,0,0,1,2,0,2,2,0,0,0,2,2A1,1,0,0,1,24,24Z"></path></svg>`;
  },

  // School/education icon
  school: function (size, color) {
    return this.createSVG(
      '<path d="M22 10v6M2 10l10-5 10 5-10 5z"></path><path d="M6 12v5c0 1.1.9 2 2 2h2a2 2 0 0 0 2-2v-5M6 12l4-2M6 12l-4-2m8 4l4-2m0 4v5c0 1.1-.9 2-2 2h-2a2 2 0 0 1-2-2v-5m0 0l-4-2m4 2l4-2"></path>',
      size,
      color,
    );
  },

  // Briefcase/work icon
  briefcase: function (size, color) {
    return this.createSVG(
      '<rect x="2" y="7" width="20" height="14" rx="2" ry="2"></rect><path d="M16 21V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v16"></path>',
      size,
      color,
    );
  },

  // Heart/health icon
  heart: function (size, color) {
    return this.createSVG(
      '<path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"></path>',
      size,
      color,
    );
  },

  // Dollar sign/money icon
  dollarSign: function (size, color) {
    return this.createSVG(
      '<line x1="12" y1="1" x2="12" y2="23"></line><path d="M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"></path>',
      size,
      color,
    );
  },

  // Book icon
  book: function (size, color) {
    return this.createSVG(
      '<path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"></path><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"></path>',
      size,
      color,
    );
  },

  // Calendar icon
  calendar: function (size, color) {
    return this.createSVG(
      '<rect x="3" y="4" width="18" height="18" rx="2" ry="2"></rect><line x1="16" y1="2" x2="16" y2="6"></line><line x1="8" y1="2" x2="8" y2="6"></line><line x1="3" y1="10" x2="21" y2="10"></line>',
      size,
      color,
    );
  },

  // Shopping bag icon
  shoppingBag: function (size, color) {
    return this.createSVG(
      '<path d="M6 2L3 6v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2V6l-3-4z"></path><line x1="3" y1="6" x2="21" y2="6"></line><path d="M16 10a4 4 0 0 1-8 0"></path>',
      size,
      color,
    );
  },

  // Car icon
  car: function (size, color) {
    return this.createSVG(
      '<path d="M5 17h14l-1-7H6z"></path><path d="M7 17c-1.1 0-2-.9-2-2s.9-2 2-2 2 .9 2 2-.9 2-2 2z"></path><path d="M17 17c-1.1 0-2-.9-2-2s.9-2 2-2 2 .9 2 2-.9 2-2 2z"></path><path d="M2 12h20M5 9l2-4h10l2 4"></path>',
      size,
      color,
    );
  },

  // Music icon
  music: function (size, color) {
    return this.createSVG(
      '<path d="M9 18V5l12-2v13"></path><circle cx="6" cy="18" r="3"></circle><circle cx="18" cy="16" r="3"></circle>',
      size,
      color,
    );
  },

  // Video icon
  video: function (size, color) {
    return this.createSVG(
      '<polygon points="23 7 16 12 23 17 23 7"></polygon><rect x="1" y="5" width="15" height="14" rx="2" ry="2"></rect>',
      size,
      color,
    );
  },

  // Camera icon
  camera: function (size, color) {
    return this.createSVG(
      '<path d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z"></path><circle cx="12" cy="13" r="4"></circle>',
      size,
      color,
    );
  },

  // Gamepad icon
  gamepad: function (size, color) {
    return this.createSVG(
      '<line x1="6" y1="12" x2="10" y2="12"></line><line x1="8" y1="10" x2="8" y2="14"></line><line x1="15" y1="13" x2="15.01" y2="13"></line><line x1="18" y1="11" x2="18.01" y2="11"></line><rect x="2" y="6" width="20" height="12" rx="2"></rect>',
      size,
      color,
    );
  },

  // Coffee icon
  coffee: function (size, color) {
    return this.createSVG(
      '<path d="M18 8h1a4 4 0 0 1 0 8h-1"></path><path d="M2 8h16v9a4 4 0 0 1-4 4H6a4 4 0 0 1-4-4V8z"></path><line x1="6" y1="1" x2="6" y2="4"></line><line x1="10" y1="1" x2="10" y2="4"></line><line x1="14" y1="1" x2="14" y2="4"></line>',
      size,
      color,
    );
  },

  // Building/office icon
  building: function (size, color) {
    return this.createSVG(
      '<path d="M3 21h18"></path><path d="M5 21V7l8-4v18"></path><path d="M19 21V11l-6-4"></path><line x1="9" y1="9" x2="9" y2="9"></line><line x1="9" y1="12" x2="9" y2="12"></line><line x1="9" y1="15" x2="9" y2="15"></line><line x1="9" y1="18" x2="9" y2="18"></line>',
      size,
      color,
    );
  },

  // Graduation cap icon (different from school)
  graduationCap: function (size, color) {
    return this.createSVG(
      '<path d="M12 2L2 7l10 5 10-5-10-5z"></path><path d="M2 17l10 5 10-5M2 12l10 5 10-5"></path>',
      size,
      color,
    );
  },

  // Wallet icon
  wallet: function (size, color) {
    return this.createSVG(
      '<path d="M21 12V7H5a2 2 0 0 1 0-4h14v4"></path><path d="M3 5v14a2 2 0 0 0 2 2h16v-5"></path><path d="M18 12a2 2 0 0 0 0 4h4v-4Z"></path>',
      size,
      color,
    );
  },

  // Plane/travel icon
  plane: function (size, color) {
    return this.createSVG(
      '<path d="M17.8 19.2 16 11l3.5-3.5C21 6 21.5 4 21 3c-1-.5-3 0-4.5 1.5L13 8 4.8 6.2c-.5-.1-.9.1-1.1.5l-.3.5c-.2.5-.1 1 .3 1.3L9 12l-2 3H4l-1 1 3 2 2 3 1-1v-3l3-2 3.5 5.3c.3.4.8.5 1.3.3l.5-.2c.4-.3.6-.7.5-1.2z"></path>',
      size,
      color,
    );
  },

  // ZIP archive icon
  zip: function (size, color) {
    return this.createSVG(
      '<path d="M9.49094 4.40235C9.1153 4.14129 8.66749 4 8.20693 4H4.25L4.09595 4.00519C2.92516 4.08436 2 5.05914 2 6.25V17.75L2.00519 17.904C2.08436 19.0748 3.05914 20 4.25 20H19.75L19.904 19.9948C21.0748 19.9156 22 18.9409 22 17.75V8.75L21.9948 8.59595L21.9785 8.43788C21.8266 7.34297 20.8867 6.5 19.75 6.5H12.022L9.64734 4.5215L9.49094 4.40235ZM13.4967 8V10.2451C13.4967 10.6593 13.8325 10.9951 14.2467 10.9951H14.9967V11.9976H14.7467C14.3325 11.9976 13.9967 12.3334 13.9967 12.7476C13.9967 13.1618 14.3325 13.4976 14.7467 13.4976H14.9967V14.9976H14.7467C14.3325 14.9976 13.9967 15.3334 13.9967 15.7476C13.9967 16.1618 14.3325 16.4976 14.7467 16.4976H14.9967V18.5H4.25L4.14823 18.4932C3.78215 18.4435 3.5 18.1297 3.5 17.75V10.499L8.20693 10.5L8.40335 10.4914C8.85906 10.4515 9.29353 10.2733 9.64734 9.9785L12.021 8H13.4967ZM16.4967 18.0004H16.7467C17.1609 18.0004 17.4967 17.6646 17.4967 17.2504C17.4967 16.8362 17.1609 16.5004 16.7467 16.5004H16.4967V15.0004H16.7467C17.1609 15.0004 17.4967 14.6646 17.4967 14.2504C17.4967 13.8362 17.1609 13.5004 16.7467 13.5004H16.4967V10.9951H17.2467C17.6609 10.9951 17.9967 10.6593 17.9967 10.2451V8H19.75L19.8518 8.00685C20.2178 8.05651 20.5 8.3703 20.5 8.75V17.75L20.4932 17.8518C20.4435 18.2178 20.1297 18.5 19.75 18.5H16.4967V18.0004ZM16.4967 8V9.49513L14.9967 9.49513V8H16.4967ZM4.25 5.5H8.20693L8.31129 5.5073C8.44893 5.52664 8.57923 5.58398 8.68706 5.67383L10.578 7.249L8.68706 8.82617L8.60221 8.88738C8.4841 8.96063 8.34729 9 8.20693 9L3.5 8.999V6.25L3.50685 6.14823C3.55651 5.78215 3.8703 5.5 4.25 5.5Z"></path>',
      size,
      color,
      true, // use fill instead of stroke
    );
  },

  // Funnel/filter icon
  funnel: function (size, color) {
    const fillAttr = `fill="${color}"`;
    const strokeAttr = `stroke="none"`;
    // Main path (outer funnel)
    const mainPath =
      '<path d="M20,43.45a.94.94,0,0,1-.51-.14,1,1,0,0,1-.49-.86V28.34L6.21,11.61A1,1,0,0,1,6,11V5.19a1,1,0,0,1,1-1H41a1,1,0,0,1,1,1V11a1,1,0,0,1-.21.61L29,28.34v9.75a1,1,0,0,1-.52.88l-8,4.36A1,1,0,0,1,20,43.45ZM8,10.66,20.79,27.39A1,1,0,0,1,21,28V40.77l6-3.27V28a1,1,0,0,1,.21-.61L40,10.66V6.19H8Z" opacity="0.9"></path>';
    // Highlight path (inner detail)
    const highlightPath =
      '<path d="M38,5V9.13a2,2,0,0,1-.41,1.21L25.41,26.27A2,2,0,0,0,25,27.48v8.23a2,2,0,0,1-1,1.75l-4,2.16v2.64l8-4.36V27.81l13-17V5Z" opacity="0.35"></path>';
    return `<svg width="${size}" height="${size}" viewBox="0 0 48 48" ${fillAttr} ${strokeAttr}>${mainPath}${highlightPath}</svg>`;
  },

  // Markdown icon
  markdown: function (size, color) {
    return this.createSVG(
      '<path d="M3 5m0 2a2 2 0 0 1 2 -2h14a2 2 0 0 1 2 2v10a2 2 0 0 1 -2 2h-14a2 2 0 0 1 -2 -2z"></path><path d="M7 15v-6l2 2l2 -2v6"></path><path d="M14 13l2 2l2 -2m-2 2v-6"></path>',
      size,
      color,
    );
  },

  // HTML icon
  html: function (size, color) {
    return this.createSVG(
      '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline><path d="M7 10h10M7 14h10M7 18h6"></path>',
      size,
      color,
    );
  },

  // PDF icon
  pdf: function (size, color) {
    return this.createSVG(
      '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline><path d="M7 10h10M7 14h8M7 18h6"></path>',
      size,
      color,
    );
  },

  // Word document icon
  word: function (size, color) {
    return this.createSVG(
      '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline><path d="M7 10h10M7 14h10M7 18h8"></path>',
      size,
      color,
    );
  },

  // Excel/Spreadsheet icon
  excel: function (size, color) {
    return this.createSVG(
      '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline><line x1="7" y1="10" x2="17" y2="10"></line><line x1="7" y1="14" x2="17" y2="14"></line><line x1="7" y1="18" x2="15" y2="18"></line>',
      size,
      color,
    );
  },

  // PowerPoint/Presentation icon
  powerpoint: function (size, color) {
    return this.createSVG(
      '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline><circle cx="10" cy="12" r="3"></circle><line x1="10" y1="9" x2="10" y2="15"></line>',
      size,
      color,
    );
  },

  // Code icon
  code: function (size, color) {
    return this.createSVG(
      '<polyline points="16 18 22 12 16 6"></polyline><polyline points="8 6 2 12 8 18"></polyline>',
      size,
      color,
    );
  },

  // JSON icon
  json: function (size, color) {
    return this.createSVG(
      '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline><path d="M8 10h8M8 14h6M8 18h8"></path>',
      size,
      color,
    );
  },

  // XML icon
  xml: function (size, color) {
    return this.createSVG(
      '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline><path d="M7 10l2 4-2 4M11 10l2 4-2 4M15 10h2"></path>',
      size,
      color,
    );
  },

  // CSV icon
  csv: function (size, color) {
    return this.createSVG(
      '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline><line x1="7" y1="10" x2="17" y2="10"></line><line x1="7" y1="14" x2="17" y2="14"></line><line x1="7" y1="18" x2="15" y2="18"></line>',
      size,
      color,
    );
  },

  // Text file icon
  text: function (size, color) {
    return this.createSVG(
      '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline><path d="M7 10h10M7 14h8M7 18h6"></path>',
      size,
      color,
    );
  },

  // ISO icon (disk icon)
  iso: function (size, color) {
    const viewBox = "0 0 32 32";
    const outerCircle =
      '<circle cx="16" cy="16" r="14" fill="none" stroke="currentColor" stroke-width="1.5"></circle>';
    const sideArcs =
      '<path d="M23.994,15.995c-0,4.416 -3.585,8 -8,8c-0.552,0 -1,0.448 -1,1c-0,0.552 0.448,1 1,1c5.519,0 10,-4.481 10,-10c-0,-0.552 -0.448,-1 -1,-1c-0.552,0 -1,0.448 -1,1Zm-16,0c-0,-4.415 3.584,-8 8,-8c0.552,0 1,-0.448 1,-1c-0,-0.552 -0.448,-1 -1,-1c-5.519,0 -10,4.481 -10,10c-0,0.552 0.448,1 1,1c0.552,0 1,-0.448 1,-1Z" fill="none" stroke="currentColor" stroke-width="1.5"></path>';
    const centerDot =
      '<circle cx="16" cy="16" r="1.5" fill="currentColor"></circle>';
    return `<svg width="${size}" height="${size}" viewBox="${viewBox}" fill="${color}" stroke="${color}" stroke-linecap="round" stroke-linejoin="round">${outerCircle}${sideArcs}${centerDot}</svg>`;
  },

  // Executable icon
  executable: function (size, color) {
    return this.createSVG(
      '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline><path d="M9 12h6M9 16h4"></path>',
      size,
      color,
    );
  },

  // Archive icon (for RAR, 7Z, TAR, etc.)
  archive: function (size, color) {
    return this.createSVG(
      '<path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"></path><polyline points="3.27 6.96 12 12.01 20.73 6.96"></polyline><line x1="12" y1="22.08" x2="12" y2="12"></line>',
      size,
      color,
    );
  },

  // Helper function to get file icon based on mime type and extension
  getFileIconName: function (mimeType, fileName) {
    if (!mimeType && !fileName) {
      return "file";
    }

    const ext = fileName ? fileName.split(".").pop()?.toLowerCase() || "" : "";

    // Check mime type first
    if (mimeType) {
      // Images
      if (mimeType.startsWith("image/")) {
        return "image";
      }

      // Videos
      if (mimeType.startsWith("video/")) {
        return "video";
      }

      // Audio
      if (mimeType.startsWith("audio/")) {
        return "music";
      }

      // PDF
      if (mimeType === "application/pdf") {
        return "pdf";
      }

      // Word documents
      if (
        mimeType === "application/msword" ||
        mimeType ===
          "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
      ) {
        return "word";
      }

      // Excel spreadsheets
      if (
        mimeType === "application/vnd.ms-excel" ||
        mimeType ===
          "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
      ) {
        return "excel";
      }

      // PowerPoint presentations
      if (
        mimeType === "application/vnd.ms-powerpoint" ||
        mimeType ===
          "application/vnd.openxmlformats-officedocument.presentationml.presentation"
      ) {
        return "powerpoint";
      }

      // ZIP archives
      if (
        mimeType === "application/zip" ||
        mimeType === "application/x-zip-compressed"
      ) {
        return "zip";
      }

      // Other archives
      if (
        mimeType === "application/x-rar-compressed" ||
        mimeType === "application/x-rar" ||
        mimeType === "application/x-7z-compressed" ||
        mimeType === "application/x-tar" ||
        mimeType === "application/gzip" ||
        mimeType === "application/x-gzip"
      ) {
        return "archive";
      }

      // Markdown
      if (mimeType === "text/markdown" || mimeType === "text/x-markdown") {
        return "markdown";
      }

      // HTML
      if (mimeType === "text/html") {
        return "html";
      }

      // JSON
      if (mimeType === "application/json" || mimeType === "text/json") {
        return "json";
      }

      // XML
      if (mimeType === "text/xml" || mimeType === "application/xml") {
        return "xml";
      }

      // CSV
      if (mimeType === "text/csv") {
        return "csv";
      }

      // Text files
      if (mimeType === "text/plain") {
        return "text";
      }

      // ISO
      if (
        mimeType === "application/x-iso9660-image" ||
        mimeType === "application/x-cd-image"
      ) {
        return "iso";
      }

      // Executables
      if (mimeType === "application/x-executable") {
        return "executable";
      }

      // Code files
      if (
        mimeType === "text/javascript" ||
        mimeType === "application/javascript" ||
        mimeType === "application/x-python" ||
        mimeType === "text/x-python" ||
        mimeType === "text/x-java" ||
        mimeType === "text/x-c" ||
        mimeType === "text/x-c++" ||
        mimeType === "text/x-csharp" ||
        mimeType === "text/css" ||
        mimeType === "application/x-sh" ||
        mimeType === "application/x-bash"
      ) {
        return "code";
      }
    }

    // Fallback to extension if mime type not recognized
    if (ext) {
      // Images
      if (
        [
          "png",
          "jpg",
          "jpeg",
          "gif",
          "webp",
          "svg",
          "bmp",
          "tiff",
          "ico",
        ].includes(ext)
      ) {
        return "image";
      }

      // Videos
      if (
        [
          "mp4",
          "avi",
          "mov",
          "wmv",
          "flv",
          "webm",
          "mkv",
          "mpeg",
          "mpg",
        ].includes(ext)
      ) {
        return "video";
      }

      // Audio
      if (["mp3", "wav", "flac", "ogg", "m4a", "aac", "wma"].includes(ext)) {
        return "music";
      }

      // Documents
      if (ext === "pdf") {
        return "pdf";
      }

      if (ext === "doc" || ext === "docx") {
        return "word";
      }

      if (ext === "xls" || ext === "xlsx") {
        return "excel";
      }

      if (ext === "ppt" || ext === "pptx") {
        return "powerpoint";
      }

      // Archives
      if (ext === "zip") {
        return "zip";
      }

      if (["rar", "7z", "tar", "gz", "bz2", "xz"].includes(ext)) {
        return "archive";
      }

      // Markdown
      if (ext === "md" || ext === "markdown") {
        return "markdown";
      }

      // HTML
      if (ext === "html" || ext === "htm") {
        return "html";
      }

      // JSON
      if (ext === "json") {
        return "json";
      }

      // XML
      if (ext === "xml") {
        return "xml";
      }

      // CSV
      if (ext === "csv") {
        return "csv";
      }

      // Text files
      if (
        ext === "txt" ||
        ext === "log" ||
        ext === "ini" ||
        ext === "conf" ||
        ext === "cfg"
      ) {
        return "text";
      }

      // ISO
      if (ext === "iso" || ext === "dmg") {
        return "iso";
      }

      // Executables
      if (["exe", "app", "deb", "rpm", "msi", "dmg", "pkg"].includes(ext)) {
        return "executable";
      }

      // Code files
      if (
        [
          "js",
          "ts",
          "jsx",
          "tsx",
          "py",
          "java",
          "c",
          "cpp",
          "cc",
          "cxx",
          "h",
          "hpp",
          "cs",
          "php",
          "rb",
          "go",
          "rs",
          "swift",
          "kt",
          "scala",
          "sh",
          "bash",
          "zsh",
          "fish",
          "ps1",
          "bat",
          "cmd",
          "css",
          "scss",
          "sass",
          "less",
          "vue",
          "svelte",
        ].includes(ext)
      ) {
        return "code";
      }
    }

    // Default fallback
    return "file";
  },
};
