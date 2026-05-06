import { useDataQuery, useDataMutation } from '@dhis2/app-runtime'
import { useCallback, useEffect, useState } from 'react'
import type { SunbirdConfig } from '@/pages/Settings'

const CONFIG_KEY = 'config'
const NAMESPACE = 'sunbird-sync'

interface DataStoreValue {
    dataStore: {
        config: SunbirdConfig
    }
}

const configQuery = {
    dataStore: {
        resource: `dataStore/${NAMESPACE}/${CONFIG_KEY}`,
    },
}

const createConfigMutation = {
    resource: `dataStore/${NAMESPACE}/${CONFIG_KEY}`,
    type: 'create' as const,
    data: ({ config }: { config: SunbirdConfig }) => config,
}

const updateConfigMutation = {
    resource: `dataStore/${NAMESPACE}/${CONFIG_KEY}`,
    type: 'update' as const,
    data: ({ config }: { config: SunbirdConfig }) => config,
}

interface UseConfigResult {
    config: SunbirdConfig | null
    loading: boolean
    saving: boolean
    error: Error | null
    saveConfig: (config: SunbirdConfig) => Promise<void>
    isConfigured: boolean
}

export const useConfig = (): UseConfigResult => {
    const [config, setConfig] = useState<SunbirdConfig | null>(null)
    const [exists, setExists] = useState(false)

    const { loading, error, refetch } = useDataQuery<DataStoreValue>(
        configQuery,
        {
            onComplete: (data) => {
                setConfig(data.dataStore as unknown as SunbirdConfig)
                setExists(true)
            },
            onError: (err) => {
                // 404 means config doesn't exist yet - not an error
                if (err.details?.httpStatusCode === 404) {
                    setExists(false)
                    setConfig(null)
                }
            },
        }
    )

    const [createMutation, { loading: creating }] = useDataMutation(
        createConfigMutation,
        {
            onComplete: () => {
                setExists(true)
                refetch()
            },
        }
    )

    const [updateMutation, { loading: updating }] = useDataMutation(
        updateConfigMutation,
        {
            onComplete: () => {
                refetch()
            },
        }
    )

    const saveConfig = useCallback(
        async (newConfig: SunbirdConfig) => {
            if (exists) {
                await updateMutation({ config: newConfig })
            } else {
                await createMutation({ config: newConfig })
            }
            setConfig(newConfig)
        },
        [exists, createMutation, updateMutation]
    )

    const isConfigured = Boolean(
        config?.sunbirdUrl &&
            config?.keycloakUrl &&
            config?.clientId &&
            config?.clientSecret &&
            config?.entityType &&
            config?.programId
    )

    // Treat 404 as not configured, not an error
    const actualError =
        error && (error as any).details?.httpStatusCode !== 404 ? error : null

    return {
        config,
        loading,
        saving: creating || updating,
        error: actualError,
        saveConfig,
        isConfigured,
    }
}
