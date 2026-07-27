export class APIError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

interface CustomRequestInit extends RequestInit {
  _isRetry?: boolean;
}

let refreshPromise: Promise<string | null> | null = null;

const getRefreshToken = async (): Promise<string | null> => {
  if (refreshPromise) {
    return refreshPromise;
  }
  
  const refreshToken = localStorage.getItem('refresh_token');
  if (!refreshToken) {
    return null;
  }
  
  refreshPromise = (async () => {
    try {
      const res = await fetch('/auth/refresh', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ refresh_token: refreshToken })
      });
      
      if (!res.ok) {
        throw new Error('Refresh failed');
      }
      
      const data = await res.json();
      localStorage.setItem('token', data.access_token);
      localStorage.setItem('refresh_token', data.refresh_token);
      return data.access_token;
    } catch (e) {
      localStorage.removeItem('token');
      localStorage.removeItem('refresh_token');
      return null;
    } finally {
      refreshPromise = null;
    }
  })();
  
  return refreshPromise;
};

export const fetchApi = async (endpoint: string, options: CustomRequestInit = {}) => {
  const token = localStorage.getItem('token');
  const headers: Record<string, string> = {
    ...(options.headers as Record<string, string> || {}),
  };
  
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }
  
  // Only set Content-Type if it's not FormData (fetch sets it automatically for FormData)
  if (options.body && typeof options.body === 'string') {
    headers['Content-Type'] = 'application/json';
  }

  let res = await fetch(endpoint, { ...options, headers });
  
  if (res.status === 401 || res.status === 403) {
    const refreshToken = localStorage.getItem('refresh_token');
    
    if (refreshToken && !options._isRetry) {
      const newAccessToken = await getRefreshToken();
      if (newAccessToken) {
        headers['Authorization'] = `Bearer ${newAccessToken}`;
        res = await fetch(endpoint, { ...options, headers, _isRetry: true });
      }
    }
    
    if (res.status === 401 || res.status === 403) {
      localStorage.removeItem('token');
      localStorage.removeItem('refresh_token');
      window.location.href = '/login';
      throw new APIError(res.status, 'Unauthorized');
    }
  }
  
  if (!res.ok) {
    let msg = 'An error occurred';
    try {
      const data = await res.json();
      msg = data.detail || msg;
    } catch (e) {
      // Ignore JSON parse error
    }
    throw new APIError(res.status, msg);
  }
  
  if (res.status === 204) {
    return null;
  }
  
  return res.json();
};
