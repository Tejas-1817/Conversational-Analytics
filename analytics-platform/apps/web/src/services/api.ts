export class APIError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

export const fetchApi = async (endpoint: string, options: RequestInit = {}) => {
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

  const res = await fetch(endpoint, { ...options, headers });
  
  if (res.status === 401 || res.status === 403) {
    localStorage.removeItem('token');
    window.location.href = '/login';
    throw new APIError(res.status, 'Unauthorized');
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
