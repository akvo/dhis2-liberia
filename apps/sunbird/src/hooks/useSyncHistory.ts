import { useDataQuery, useDataMutation } from '@dhis2/app-runtime'
import { useCallback, useState } from 'react'
import type { SyncLogEntry } from '@/pages/History'

const HISTORY_KEY = 'history'
const NAMESPACE = 'sunbird-sync'

// Worker writes entries in this format (org unit based sync)
interface WorkerHistoryEntry {
    id: string
    timestamp: string
    mappingId: string
    entityType: string
    totalCount: number
    successCount: number
    errorCount: number
    results: Array<{
        orgUnitId: string
        orgUnitName: string
        status: string
        osid?: string
        error?: string
    }>
}

interface DataStoreValue {
    dataStore: WorkerHistoryEntry[]
}

const historyQuery = {
    dataStore: {
        resource: `dataStore/${NAMESPACE}/${HISTORY_KEY}`,
    },
}

const updateHistoryMutation = {
    resource: `dataStore/${NAMESPACE}/${HISTORY_KEY}`,
    type: 'update' as const,
    data: ({ history }: { history: WorkerHistoryEntry[] }) => history,
}

// Convert worker entry to app log format
function workerEntryToLog(entry: WorkerHistoryEntry): SyncLogEntry {
    // Determine status
    let status: SyncLogEntry['status'] = 'success'
    if (entry.errorCount > 0 && entry.successCount > 0) {
        status = 'partial'
    } else if (entry.errorCount > 0 && entry.successCount === 0) {
        status = 'failed'
    }

    // Build details from error results
    const errorResults = entry.results?.filter(r => r.status === 'error' && r.error) || []
    const details = errorResults.length > 0
        ? errorResults.map(r => `${r.orgUnitName}: ${r.error}`).join('\n')
        : undefined

    return {
        id: entry.id,
        timestamp: new Date(entry.timestamp).toLocaleString(),
        recordCount: entry.totalCount,
        successCount: entry.successCount,
        errorCount: entry.errorCount,
        status,
        details,
    }
}

interface UseSyncHistoryResult {
    logs: SyncLogEntry[]
    loading: boolean
    refetchHistory: () => void
    clearHistory: () => Promise<void>
}

export const useSyncHistory = (): UseSyncHistoryResult => {
    const [logs, setLogs] = useState<SyncLogEntry[]>([])

    const { loading, refetch } = useDataQuery<DataStoreValue>(historyQuery, {
        onComplete: (data) => {
            // History is stored as an array of entries
            const historyArray = data.dataStore as unknown as WorkerHistoryEntry[]

            if (Array.isArray(historyArray)) {
                // Convert to log format and sort by timestamp (most recent first)
                const convertedLogs = historyArray.map(workerEntryToLog)
                convertedLogs.sort((a, b) => {
                    // Parse back to compare dates
                    return new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime()
                })
                setLogs(convertedLogs)
            } else {
                setLogs([])
            }
        },
        onError: (err) => {
            if ((err as any).details?.httpStatusCode === 404) {
                setLogs([])
            }
        },
    })

    const [updateMutation] = useDataMutation(updateHistoryMutation)

    const refetchHistory = useCallback(() => {
        refetch()
    }, [refetch])

    const clearHistory = useCallback(async () => {
        await updateMutation({ history: [] })
        setLogs([])
        refetch()
    }, [updateMutation, refetch])

    return {
        logs,
        loading,
        refetchHistory,
        clearHistory,
    }
}
