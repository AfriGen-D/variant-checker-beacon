import axios, { AxiosError, AxiosInstance } from 'axios';
import type { BeaconError } from './types';

// Get API base URL from environment.
//
// Defaults to '' — a RELATIVE /api — because every real deployment serves the
// UI and the API behind one proxy (nginx routes /api/* to the API container).
// Defaulting to an absolute localhost URL is a production landmine: the value
// is inlined into the browser bundle at build time, and `'' || 'http://…'`
// falls through, so even explicitly passing an empty build-arg produced a
// bundle that called localhost:8000 from users' browsers.
//
// Running the frontend standalone (no proxy) must set the variable explicitly;
// compose/docker-compose-frontend.yml already does.
const API_BASE_URL = process.env.NEXT_PUBLIC_BEACON_API_URL ?? '';

// Create Axios instance
export const beaconClient: AxiosInstance = axios.create({
  baseURL: `${API_BASE_URL}/api`,
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request interceptor
beaconClient.interceptors.request.use(
  (config) => {
    // Add timestamp to prevent caching issues
    if (config.params) {
      config.params._t = Date.now();
    } else {
      config.params = { _t: Date.now() };
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// Response interceptor for error handling
beaconClient.interceptors.response.use(
  (response) => {
    return response;
  },
  (error: AxiosError<BeaconError>) => {
    // Handle different error types
    if (error.response) {
      const status = error.response.status;
      const data = error.response.data;

      switch (status) {
        case 400:
          // Bad Request - validation error
          console.error('Validation error:', data);
          error.message = data?.error?.errorMessage || 'Invalid query parameters';
          break;

        case 404:
          // Not Found
          error.message = 'Resource not found';
          break;

        case 429:
          // Rate Limit Exceeded
          error.message = 'Rate limit exceeded. Please try again later.';
          break;

        case 500:
          // Internal Server Error
          error.message = 'Server error. Please try again later.';
          break;

        case 503:
          // Service Unavailable
          error.message = 'Service temporarily unavailable';
          break;

        default:
          error.message = data?.error?.errorMessage || 'An unexpected error occurred';
      }
    } else if (error.request) {
      // Request made but no response
      error.message = 'No response from server. Please check your connection.';
    } else {
      // Something else happened
      error.message = error.message || 'Request failed';
    }

    return Promise.reject(error);
  }
);

// Helper function to check if error is a rate limit error
export const isRateLimitError = (error: unknown): boolean => {
  return axios.isAxiosError(error) && error.response?.status === 429;
};

// Helper function to check if error is a validation error
export const isValidationError = (error: unknown): boolean => {
  return axios.isAxiosError(error) && error.response?.status === 400;
};

// Helper function to get error message
export const getErrorMessage = (error: unknown): string => {
  if (axios.isAxiosError(error)) {
    return error.message;
  }
  if (error instanceof Error) {
    return error.message;
  }
  return 'An unknown error occurred';
};
