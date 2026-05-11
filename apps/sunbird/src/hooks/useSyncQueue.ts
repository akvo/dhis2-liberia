import { useDataQuery, useDataMutation } from '@dhis2/app-runtime'
import { useCallback, useState } from 'react'

const NAMESPACE = 'sunbird-sync'
const QUEUE_KEY = 'queue'

interface SyncRequest {
    id: string
    type: 'all' | 'selected'
    teiIds?: string[]
    status: 'pending' | 'processing' | 'completed'
    createdAt: string
}

interface QueueData {
    requests: SyncRequest[]
    lastCleared?: string
}

interface DataStoreValue {
    dataStore: QueueData
}

const queueQuery = {
    dataStore: {
        resource: `dataStore/${NAMESPACE}/${QUEUE_KEY}`,
    },
}

const createQueueMutation = {
    resource: `dataStore/${NAMESPACE}/${QUEUE_KEY}`,
    type: 'create' as const,
    data: ({ queue }: { queue: QueueData }) => queue,
}

const updateQueueMutation = {
    resource: `dataStore/${NAMESPACE}/${QUEUE_KEY}`,
    type: 'update' as const,
    data: ({ queue }: { queue: QueueData }) => queue,
}

interface UseSyncQueueResult {
    queueSyncRequest: (teiIds?: string[]) => Promise<string>
    loading: boolean
    error: Error | null
}

export const useSyncQueue = (): UseSyncQueueResult => {
    const [loading, setLoading] = useState(false)
    const [error, setError] = useState<Error | null>(null)

    const { refetch } = useDataQuery<DataStoreValue>(queueQuery, {
        lazy: true,
    })

    const [createMutation] = useDataMutation(createQueueMutation)
    const [updateMutation] = useDataMutation(updateQueueMutation)

    const queueSyncRequest = useCallback(
        async (teiIds?: string[]): Promise<string> => {
            setLoading(true)
            setError(null)

            try {
                // Generate unique request ID
                const requestId = `sync-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`

                const newRequest: SyncRequest = {
                    id: requestId,
                    type: teiIds && teiIds.length > 0 ? 'selected' : 'all',
                    teiIds: teiIds && teiIds.length > 0 ? teiIds : undefined,
                    status: 'pending',
                    createdAt: new Date().toISOString(),
                }

                // Try to fetch existing queue
                let currentQueue: QueueData = { requests: [] }
                let exists = false
                try {
                    const result = await refetch()
                    if (result?.dataStore) {
                        currentQueue = result.dataStore as unknown as QueueData
                        exists = true
                    }
                } catch {
                    // Queue doesn't exist yet
                    exists = false
                }

                // Add new request to queue
                const updatedQueue: QueueData = {
                    ...currentQueue,
                    requests: [...(currentQueue.requests || []), newRequest],
                }

                // Save queue - use local `exists` variable, not stale state
                if (exists) {
                    await updateMutation({ queue: updatedQueue })
                } else {
                    await createMutation({ queue: updatedQueue })
                }

                return requestId
            } catch (err) {
                const error = err instanceof Error ? err : new Error('Failed to queue sync request')
                setError(error)
                throw error
            } finally {
                setLoading(false)
            }
        },
        [refetch, createMutation, updateMutation]
    )

    return {
        queueSyncRequest,
        loading,
        error,
    }
}
