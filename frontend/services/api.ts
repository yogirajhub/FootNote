import axios from 'axios';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api';
// Demo user MVP
const USER_ID = 'demo_user_001';

export const api = axios.create({
  baseURL: API_URL,
  headers: {
    'x-user-id': USER_ID,
  },
});
