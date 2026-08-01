import axios from 'axios';

const api = axios.create({
  baseURL: 'http://localhost:8000',
  timeout: 120000, // 2 min — video generation can be slow
});

export default api;
