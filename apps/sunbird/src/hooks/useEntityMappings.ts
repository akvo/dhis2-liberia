import { useDataQuery, useDataMutation } from '@dhis2/app-runtime'
import { useCallback, useState, useEffect } from 'react'
import type { EntityMapping } from '@/types'

const NAMESPACE = 'sunbird-sync'
const KEY = 'entity-mappings'

const query = {
    mappings: {
        resource: `dataStore/${NAMESPACE}/${KEY}`,
    },
}

const createMutation = {
    resource: `dataStore/${NAMESPACE}/${KEY}`,
    type: 'create' as const,
    data: ({ mappings }: { mappings: EntityMapping[] }) => mappings,
}

const updateMutation = {
    resource: `dataStore/${NAMESPACE}/${KEY}`,
    type: 'update' as const,
    data: ({ mappings }: { mappings: EntityMapping[] }) => mappings,
}

interface UseEntityMappingsResult {
    mappings: EntityMapping[]
    loading: boolean
    saving: boolean
    error: Error | null
    addMapping: (mapping: EntityMapping) => Promise<void>
    updateMapping: (mapping: EntityMapping) => Promise<void>
    deleteMapping: (id: string) => Promise<void>
    refetch: () => void
}

export const useEntityMappings = (): UseEntityMappingsResult => {
    const [mappings, setMappings] = useState<EntityMapping[]>([])
    const [exists, setExists] = useState(false)

    const { loading, error, refetch } = useDataQuery<{ mappings: EntityMapping[] }>(
        query,
        {
            onComplete: (data) => {
                const rawMappings = data.mappings as unknown
                if (Array.isArray(rawMappings)) {
                    setMappings(rawMappings as EntityMapping[])
                } else {
                    setMappings([])
                }
                setExists(true)
            },
            onError: (err) => {
                // 404 means key doesn't exist yet
                if ((err as any).details?.httpStatusCode === 404) {
                    setExists(false)
                    setMappings([])
                }
            },
        }
    )

    const [createMutate, { loading: creating }] = useDataMutation(createMutation, {
        onComplete: () => {
            setExists(true)
            refetch()
        },
    })

    const [updateMutate, { loading: updating }] = useDataMutation(updateMutation, {
        onComplete: () => {
            refetch()
        },
    })

    const saveMappings = useCallback(
        async (newMappings: EntityMapping[]) => {
            if (exists) {
                await updateMutate({ mappings: newMappings })
            } else {
                await createMutate({ mappings: newMappings })
            }
            setMappings(newMappings)
        },
        [exists, createMutate, updateMutate]
    )

    const addMapping = useCallback(
        async (mapping: EntityMapping) => {
            const newMappings = [...mappings, mapping]
            await saveMappings(newMappings)
        },
        [mappings, saveMappings]
    )

    const updateMapping = useCallback(
        async (mapping: EntityMapping) => {
            const newMappings = mappings.map((m) =>
                m.id === mapping.id ? mapping : m
            )
            await saveMappings(newMappings)
        },
        [mappings, saveMappings]
    )

    const deleteMapping = useCallback(
        async (id: string) => {
            const newMappings = mappings.filter((m) => m.id !== id)
            await saveMappings(newMappings)
        },
        [mappings, saveMappings]
    )

    // Treat 404 as not an error
    const actualError =
        error && (error as any).details?.httpStatusCode !== 404 ? error : null

    return {
        mappings,
        loading,
        saving: creating || updating,
        error: actualError,
        addMapping,
        updateMapping,
        deleteMapping,
        refetch,
    }
}
