import { useDataQuery, useDataMutation } from '@dhis2/app-runtime'
import { useCallback, useState } from 'react'
import type { SyncLogEntry } from '@/pages/History'

const HISTORY_KEY = 'history'
const NAMESPACE = 'sunbird-sync'

interface DataStoreValue {
    dataStore: {
        logs: SyncLogEntry[]
    }
}

const historyQuery = {
    dataStore: {
        resource: `dataStore/${NAMESPACE}/${HISTORY_KEY}`,
    },
}

const createHistoryMutation = {
    resource: `dataStore/${NAMESPACE}/${HISTORY_KEY}`,
    type: 'create' as const,
    data: ({ logs }: { logs: SyncLogEntry[] }) => ({ logs }),
}

const updateHistoryMutation = {
    resource: `dataStore/${NAMESPACE}/${HISTORY_KEY}`,
    type: 'update' as const,
    data: ({ logs }: { logs: SyncLogEntry[] }) => ({ logs }),
}

interface UseSyncHistoryResult {
    logs: SyncLogEntry[]
    loading: boolean
    addLog: (entry: Omit<SyncLogEntry, 'id'>) => Promise<void>
    clearHistory: () => Promise<void>
}

export const useSyncHistory = (): UseSyncHistoryResult => {
    const [logs, setLogs] = useState<SyncLogEntry[]>([])
    const [exists, setExists] = useState(false)

    const { loading, refetch } = useDataQuery<DataStoreValue>(historyQuery, {
        onComplete: (data) => {
            const historyData = data.dataStore as unknown as { logs: SyncLogEntry[] }
            setLogs(historyData.logs || [])
            setExists(true)
        },
        onError: (err) => {
            if ((err as any).details?.httpStatusCode === 404) {
                setExists(false)
                setLogs([])
            }
        },
    })

    const [createMutation] = useDataMutation(createHistoryMutation, {
        onComplete: () => {
            setExists(true)
            refetch()
        },
    })

    const [updateMutation] = useDataMutation(updateHistoryMutation, {
        onComplete: () => {
            refetch()
        },
    })

    const addLog = useCallback(
        async (entry: Omit<SyncLogEntry, 'id'>) => {
            const newLog: SyncLogEntry = {
                ...entry,
                id: `${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
            }
            const newLogs = [newLog, ...logs].slice(0, 100) // Keep last 100 entries

            if (exists) {
                await updateMutation({ logs: newLogs })
            } else {
                await createMutation({ logs: newLogs })
            }
            setLogs(newLogs)
        },
        [exists, logs, createMutation, updateMutation]
    )

    const clearHistory = useCallback(async () => {
        if (exists) {
            await updateMutation({ logs: [] })
        }
        setLogs([])
    }, [exists, updateMutation])

    return {
        logs,
        loading,
        addLog,
        clearHistory,
    }
}
