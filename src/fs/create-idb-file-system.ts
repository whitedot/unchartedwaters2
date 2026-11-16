// Read the old browser save once when the server has no save yet.
export function readLegacySave(name: string, key: string): Promise<Uint8Array | null> {
  return new Promise((resolve, reject) => {
    const open = indexedDB.open(name, 1);
    open.onerror = () => reject(new Error("기존 브라우저 세이브를 열 수 없습니다."));
    open.onupgradeneeded = () => open.result.createObjectStore("files");
    open.onsuccess = () => {
      const db = open.result;
      const request = db.transaction("files").objectStore("files").get(key);
      request.onsuccess = () => { db.close(); resolve(request.result ?? null); };
      request.onerror = () => { db.close(); reject(new Error("기존 세이브를 읽을 수 없습니다.")); };
    };
  });
}
