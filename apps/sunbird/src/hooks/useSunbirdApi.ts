import { useState, useCallback } from 'react'
import type { SunbirdConfig } from '@/pages/Settings'

interface TokenResponse {
    access_token: string
    token_type: string
    expires_in: number
}

interface TestResult {
    success: boolean
    message: string
    details?: string
}

export const useSunbirdApi = () => {
    const [testing, setTesting] = useState(false)
    const [testResult, setTestResult] = useState<TestResult | null>(null)

    const getToken = async (config: SunbirdConfig): Promise<string> => {
        const response = await fetch(config.keycloakUrl, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/x-www-form-urlencoded',
            },
            body: new URLSearchParams({
                client_id: config.clientId,
                client_secret: config.clientSecret,
                grant_type: 'client_credentials',
            }),
        })

        if (!response.ok) {
            const text = await response.text()
            throw new Error(`Keycloak auth failed: ${response.status} - ${text}`)
        }

        const data: TokenResponse = await response.json()
        return data.access_token
    }

    const testConnection = useCallback(async (config: SunbirdConfig) => {
        setTesting(true)
        setTestResult(null)

        try {
            // Step 1: Get OAuth token from Keycloak
            const token = await getToken(config)

            // Step 2: Test Sunbird RC API
            const apiUrl = `${config.sunbirdUrl}/${config.entityType}`
            const response = await fetch(apiUrl, {
                method: 'GET',
                headers: {
                    'Accept': 'application/json',
                    'Authorization': `Bearer ${token}`,
                },
            })

            if (response.ok) {
                setTestResult({
                    success: true,
                    message: 'Connection successful!',
                    details: `Successfully connected to Sunbird RC (${config.entityType})`,
                })
            } else {
                const text = await response.text()
                setTestResult({
                    success: false,
                    message: `Sunbird RC API error: ${response.status}`,
                    details: text,
                })
            }
        } catch (error) {
            const errorMessage = error instanceof Error ? error.message : 'Unknown error'

            // Check for CORS error
            if (errorMessage.includes('Failed to fetch') || errorMessage.includes('NetworkError')) {
                setTestResult({
                    success: false,
                    message: 'Connection failed (CORS or network error)',
                    details: 'The browser cannot directly connect to Sunbird RC. This may be due to CORS restrictions. The sync functionality will need to use DHIS2 Routes API for server-side proxying.',
                })
            } else {
                setTestResult({
                    success: false,
                    message: 'Connection failed',
                    details: errorMessage,
                })
            }
        } finally {
            setTesting(false)
        }
    }, [])

    const clearResult = useCallback(() => {
        setTestResult(null)
    }, [])

    return {
        testConnection,
        testing,
        testResult,
        clearResult,
    }
}
