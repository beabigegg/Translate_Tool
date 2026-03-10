import { get, post } from './client.js';
export const createJob = (formData) => post('/api/jobs', formData);
export const fetchJobStatus = (jobId) => get(`/api/jobs/${jobId}`);
export const cancelJob = (jobId) => post(`/api/jobs/${jobId}/cancel`);
