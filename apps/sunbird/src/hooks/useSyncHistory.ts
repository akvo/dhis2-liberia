import { useDataQuery, useDataMutation } from '@dhis2/app-runtime'
import { useCallback, useState } from 'react'
import type { SyncLogEntry } from '@/pages/History'

const HISTORY_KEY = 'history'
const NAMESPACE = 'sunbird-sync'

// Worker writes entries in this format
interface WorkerEntry {
    requestId: string
    type: string
    success: boolean
    total: number
    synced: number
    failed: number
    errors: Array<{ teiId?: string; error: string }>
    startedAt: string
    finishedAt: string
}

interface HistoryData {
    entries?: WorkerEntry[]
    logs?: SyncLogEntry[]
}

interface DataStoreValue {
    dataStore: HistoryData
}

const historyQuery = {
    dataStore: {
        resource: `dataStore/${NAMESPACE}/${HISTORY_KEY}`,
    },
}

const updateHistoryMutation = {
    resource: `dataStore/${NAMESPACE}/${HISTORY_KEY}`,
    type: 'update' as const,
    data: ({ history }: { history: HistoryData }) => history,
}

// Convert worker entry to app log format
function workerEntryToLog(entry: WorkerEntry): SyncLogEntry {
    return {
        id: entry.requestId,
        timestamp: entry.finishedAt || entry.startedAt,
        recordCount: entry.total,
        successCount: entry.synced,
        errorCount: entry.failed,
        status: entry.success ? 'success' : 'failed',
        details: entry.errors?.length > 0
            ? entry.errors.map(e => e.error).join('; ')
            : undefined,
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
    const [historyData, setHistoryData] = useState<HistoryData | null>(null)

    const { loading, refetch } = useDataQuery<DataStoreValue>(historyQuery, {
        onComplete: (data) => {
            const history = data.dataStore as unknown as HistoryData
            setHistoryData(history)

            // Merge worker entries with any existing logs
            const workerLogs = (history.entries || []).map(workerEntryToLog)
            // Sort by timestamp, most recent first
            workerLogs.sort((a, b) =>
                new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime()
            )
            setLogs(workerLogs)
        },
        onError: (err) => {
            if ((err as any).details?.httpStatusCode === 404) {
                setHistoryData(null)
                setLogs([])
            }
        },
    })

    const [updateMutation] = useDataMutation(updateHistoryMutation)

    const refetchHistory = useCallback(() => {
        refetch()
    }, [refetch])

    const clearHistory = useCallback(async () => {
        if (historyData) {
            await updateMutation({ history: { entries: [], logs: [] } })
            refetch()
        }
        setLogs([])
    }, [historyData, updateMutation, refetch])

    return {
        logs,
        loading,
        refetchHistory,
        clearHistory,
    }
}
