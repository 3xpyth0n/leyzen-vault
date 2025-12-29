class KeyManager {
  constructor() {
    this.dbName = "leyzen_vault_keys";
    this.dbVersion = 1;
    this.storeName = "keys";
    this.db = null;
  }

  async init() {
    return new Promise((resolve, reject) => {
      const request = indexedDB.open(this.dbName, this.dbVersion);

      request.onerror = () => reject(request.error);
      request.onsuccess = () => {
        this.db = request.result;
        resolve();
      };

      request.onupgradeneeded = (event) => {
        const db = event.target.result;
        if (!db.objectStoreNames.contains(this.storeName)) {
          db.createObjectStore(this.storeName);
        }
      };
    });
  }

  async deriveUserMasterKey(password, salt = null) {
    if (!salt) {
      salt = crypto.getRandomValues(new Uint8Array(32));
    }

    const encoder = new TextEncoder();
    const passwordData = encoder.encode(password);

    const keyMaterial = await crypto.subtle.importKey(
      "raw",
      passwordData,
      "PBKDF2",
      false,
      ["deriveBits", "deriveKey"],
    );

    const masterKey = await crypto.subtle.deriveBits(
      {
        name: "PBKDF2",
        salt: salt,
        iterations: 600000,
        hash: "SHA-256",
      },
      keyMaterial,
      256,
    );

    return {
      masterKey: new Uint8Array(masterKey),
      salt: salt,
    };
  }

  async deriveFolderKey(masterKey, folderPath) {
    const pathString = folderPath.join("/");
    const encoder = new TextEncoder();
    const info = encoder.encode(`folder:${pathString}`);

    const keyMaterial = await crypto.subtle.importKey(
      "raw",
      masterKey,
      {
        name: "HKDF",
        hash: "SHA-256",
      },
      false,
      ["deriveBits"],
    );

    const salt = new TextEncoder().encode("leyzen-vault-hkdf-salt-2024-!!!!");
    const folderKey = await crypto.subtle.deriveBits(
      {
        name: "HKDF",
        salt: salt,
        info: info,
        hash: "SHA-256",
      },
      keyMaterial,
      256,
    );

    return new Uint8Array(folderKey);
  }

  async encryptFolderName(folderName, folderKey) {
    const encoder = new TextEncoder();
    const nameData = encoder.encode(folderName);
    const hashBuffer = await crypto.subtle.digest("SHA-256", nameData);
    const nameHash = Array.from(new Uint8Array(hashBuffer))
      .map((b) => b.toString(16).padStart(2, "0"))
      .join("");

    const iv = crypto.getRandomValues(new Uint8Array(12));
    const key = await crypto.subtle.importKey(
      "raw",
      folderKey,
      {
        name: "AES-GCM",
        length: 256,
      },
      false,
      ["encrypt"],
    );

    const encryptedBuffer = await crypto.subtle.encrypt(
      {
        name: "AES-GCM",
        iv: iv,
      },
      key,
      nameData,
    );

    const combined = new Uint8Array(iv.length + encryptedBuffer.byteLength);
    combined.set(iv, 0);
    combined.set(new Uint8Array(encryptedBuffer), iv.length);

    return {
      encrypted: combined,
      nameHash: nameHash,
    };
  }

  async decryptFolderName(encryptedData, folderKey) {
    const iv = encryptedData.slice(0, 12);
    const ciphertext = encryptedData.slice(12);

    const key = await crypto.subtle.importKey(
      "raw",
      folderKey,
      {
        name: "AES-GCM",
        length: 256,
      },
      false,
      ["decrypt"],
    );

    const decryptedBuffer = await crypto.subtle.decrypt(
      {
        name: "AES-GCM",
        iv: iv,
      },
      key,
      ciphertext,
    );

    const decoder = new TextDecoder();
    return decoder.decode(decryptedBuffer);
  }

  async storeMasterKey(masterKey, salt) {
    await this.init();

    const transaction = this.db.transaction([this.storeName], "readwrite");
    const store = transaction.objectStore(this.storeName);

    await Promise.all([
      new Promise((resolve, reject) => {
        const request = store.put(Array.from(masterKey), "master_key");
        request.onsuccess = () => resolve();
        request.onerror = () => reject(request.error);
      }),
      new Promise((resolve, reject) => {
        const request = store.put(Array.from(salt), "salt");
        request.onsuccess = () => resolve();
        request.onerror = () => reject(request.error);
      }),
    ]);
  }

  async getMasterKey() {
    await this.init();

    const transaction = this.db.transaction([this.storeName], "readonly");
    const store = transaction.objectStore(this.storeName);

    return new Promise((resolve, reject) => {
      const masterKeyRequest = store.get("master_key");
      const saltRequest = store.get("salt");

      let masterKeyData = null;
      let saltData = null;
      let completed = 0;

      const checkComplete = () => {
        completed++;
        if (completed === 2) {
          if (masterKeyData && saltData) {
            resolve({
              masterKey: new Uint8Array(masterKeyData),
              salt: new Uint8Array(saltData),
            });
          } else {
            resolve(null);
          }
        }
      };

      masterKeyRequest.onsuccess = () => {
        masterKeyData = masterKeyRequest.result;
        checkComplete();
      };
      masterKeyRequest.onerror = () => reject(masterKeyRequest.error);

      saltRequest.onsuccess = () => {
        saltData = saltRequest.result;
        checkComplete();
      };
      saltRequest.onerror = () => reject(saltRequest.error);
    });
  }

  async clearKeys() {
    await this.init();

    const transaction = this.db.transaction([this.storeName], "readwrite");
    const store = transaction.objectStore(this.storeName);

    await Promise.all([
      new Promise((resolve, reject) => {
        const request = store.delete("master_key");
        request.onsuccess = () => resolve();
        request.onerror = () => reject(request.error);
      }),
      new Promise((resolve, reject) => {
        const request = store.delete("salt");
        request.onsuccess = () => resolve();
        request.onerror = () => reject(request.error);
      }),
    ]);
  }

  arrayToBase64url(array) {
    const base64 = btoa(String.fromCharCode(...array));
    return base64.replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
  }

  base64urlToArray(base64url) {
    const base64 = base64url.replace(/-/g, "+").replace(/_/g, "/");
    const padding = base64.length % 4;
    const paddedBase64 = base64 + "=".repeat(padding ? 4 - padding : 0);
    const binaryString = atob(paddedBase64);
    const bytes = new Uint8Array(binaryString.length);
    for (let i = 0; i < binaryString.length; i++) {
      bytes[i] = binaryString.charCodeAt(i);
    }
    return bytes;
  }
}

if (typeof window !== "undefined") {
  window.KeyManager = KeyManager;
}
