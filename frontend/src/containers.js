import { request } from "./api";

function name(value) {
  return encodeURIComponent(value);
}

export function containerAction(id, action) {
  return request(`/api/v1/containers/${id}/actions/${action}`, { method: "POST" });
}

export function updateContainer(id) {
  return request(`/api/v1/containers/${id}/actions/update`, { method: "POST" });
}

export function deleteContainer(id, keepVolume = true) {
  return request(`/api/v1/containers/${id}?keep_volume=${keepVolume}`, { method: "DELETE" });
}

export function listBackups(containerName) {
  return request(`/api/v1/containers/${name(containerName)}/backups`);
}

export function createBackup(containerName) {
  return request(`/api/v1/containers/${name(containerName)}/backups`, { method: "POST" });
}

export function deleteBackup(containerName, archive) {
  return request(
    `/api/v1/containers/${name(containerName)}/backups/${name(archive)}`,
    { method: "DELETE" },
  );
}

export function restoreBackup(containerName, archive, confirm) {
  return request(
    `/api/v1/containers/${name(containerName)}/backups/${name(archive)}/restore`,
    { method: "POST", body: JSON.stringify({ confirm }) },
  );
}

export function setLink(containerName, url) {
  return request(`/api/v1/containers/${name(containerName)}/link`, {
    method: "POST",
    body: JSON.stringify({ url }),
  });
}

export function setGroup(containerName, groupId) {
  return request(`/api/v1/containers/${name(containerName)}/group`, {
    method: "POST",
    body: JSON.stringify({ group_id: groupId ? Number(groupId) : null }),
  });
}

export function saveCheck(containerName, payload) {
  return request(`/api/v1/containers/${name(containerName)}/check`, {
    method: "PUT",
    body: JSON.stringify(payload),
  });
}

export function loadLogs(containerName, tail = 300) {
  return request(`/api/v1/containers/${name(containerName)}/logs?tail=${tail}`);
}
