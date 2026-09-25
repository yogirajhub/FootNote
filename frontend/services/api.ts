import axios from 'axios';

const isServer = typeof window === 'undefined';
const API_URL = isServer
  ? (process.env.INTERNAL_API_URL || process.env.NEXT_PUBLIC_API_URL || 'http://backend:8000/api')
  : '/api';
// Demo user MVP
const USER_ID = 'demo_user_001';

export const api = axios.create({
  baseURL: API_URL,
  headers: {
    'x-user-id': USER_ID,
  },
});
