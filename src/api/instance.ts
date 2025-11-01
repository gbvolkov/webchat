import axios, { AxiosError } from 'axios'

export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8009/api'

export const DefaultAPIInstance = axios.create({
    baseURL: API_BASE_URL,
})

export const onRejectedResponse = async (payload: AxiosError) => Promise.reject(payload)

DefaultAPIInstance.interceptors.response.use(
    (response) => response,
    (error) => onRejectedResponse(error),
)
