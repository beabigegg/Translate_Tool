import { get, post } from './client.js';
export const createMediaJob = (formData) => post('/api/media/jobs', formData);
export const fetchMediaJobStatus = (jobId) => get(`/api/media/jobs/${jobId}`);
export const cancelMediaJob = (jobId) => post(`/api/media/jobs/${jobId}/cancel`);
export const fetchTranscript = (jobId) => get(`/api/media/jobs/${jobId}/transcript`);
export const mediaDownloadUrl = (jobId) => `/api/media/jobs/${jobId}/download`;
