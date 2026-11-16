const endpoint = "/api/save";

export async function openServerSave() {
  const response = await fetch(endpoint, { cache: "no-store" });
  if (!response.ok) throw new Error("서버 세이브를 불러올 수 없습니다.");
  let revision = response.headers.get("ETag");
  const data = response.status === 204 ? null : new Uint8Array(await response.arrayBuffer());
  if (data && (!revision || data.length !== 333551)) {
    throw new Error("서버 세이브 응답을 확인할 수 없습니다.");
  }

  return {
    data,
    async write(bytes: Uint8Array) {
      const result = await fetch(endpoint, {
        method: "PUT",
        headers: {
          "Content-Type": "application/octet-stream",
          ...(revision ? { "If-Match": revision } : { "If-None-Match": "*" }),
        },
        body: bytes,
      });
      if (result.status === 412) {
        throw new Error("다른 창에서 저장했습니다. 새로고침해 서버 세이브를 불러오세요.");
      }
      const next = result.headers.get("ETag");
      if (result.status !== 204 || !next) throw new Error("서버 저장에 실패했습니다. 게임에서 다시 저장하세요.");
      revision = next;
    },
  };
}
