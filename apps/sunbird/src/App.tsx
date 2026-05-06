import i18n from '@dhis2/d2-i18n'
import { CircularLoader, NoticeBox } from '@dhis2/ui'
import React, { FC, useState, useCallback } from 'react'
import classes from '@/App.module.css'
import { Navigation, PageKey } from '@/components'
import { useConfig, useSyncHistory, usePrograms, usePendingTeis } from '@/hooks'
import { Dashboard, Settings, Sync, History, SunbirdConfig } from '@/pages'

const MyApp: FC = () => {
    const [currentPage, setCurrentPage] = useState<PageKey>('dashboard')
    const [historyPage, setHistoryPage] = useState(1)

    // Hooks for data
    const { config, loading: configLoading, saving, saveConfig, isConfigured, error: configError } = useConfig()
    const { logs, loading: historyLoading, addLog, clearHistory } = useSyncHistory()
    const { programs, loading: programsLoading } = usePrograms()
    const { records: syncRecords, loading: teisLoading, refetch: refetchTeis, stats: teiStats } = usePendingTeis(config?.programId)

    const [syncing, setSyncing] = useState(false)

    const handleNavigate = useCallback((page: PageKey) => {
        setCurrentPage(page)
    }, [])

    const handleSaveConfig = useCallback(
        async (newConfig: SunbirdConfig) => {
            await saveConfig(newConfig)
        },
        [saveConfig]
    )

    const handleSync = useCallback(
        async (selectedIds: string[]) => {
            setSyncing(true)
            try {
                // TODO: Implement actual sync logic
                await addLog({
                    timestamp: new Date().toISOString(),
                    recordCount: selectedIds.length,
                    successCount: selectedIds.length,
                    errorCount: 0,
                    status: 'success',
                })
            } catch (err) {
                await addLog({
                    timestamp: new Date().toISOString(),
                    recordCount: selectedIds.length,
                    successCount: 0,
                    errorCount: selectedIds.length,
                    status: 'failed',
                    details: err instanceof Error ? err.message : 'Unknown error',
                })
            } finally {
                setSyncing(false)
            }
        },
        [addLog]
    )

    const handleRefresh = useCallback(() => {
        refetchTeis()
    }, [refetchTeis])

    const handleClearHistory = useCallback(async () => {
        await clearHistory()
    }, [clearHistory])

    const handleHistoryPageChange = useCallback((page: number) => {
        setHistoryPage(page)
    }, [])

    // Calculate dashboard stats
    const stats = {
        totalSynced: teiStats.synced,
        lastSyncTime: logs.length > 0 ? new Date(logs[0].timestamp).toLocaleString() : null,
        pendingCount: teiStats.pending,
        errorCount: teiStats.failed,
    }

    if (configError) {
        return (
            <div className={classes.container}>
                <NoticeBox error title={i18n.t('Error')}>
                    {i18n.t('Failed to load configuration: {{message}}', {
                        message: configError.message,
                    })}
                </NoticeBox>
            </div>
        )
    }

    const isLoading = configLoading || historyLoading || (isConfigured && teisLoading)

    if (isLoading) {
        return (
            <div className={classes.loadingContainer}>
                <CircularLoader />
            </div>
        )
    }

    const renderPage = () => {
        switch (currentPage) {
            case 'dashboard':
                return (
                    <Dashboard
                        stats={stats}
                        loading={false}
                        isConfigured={isConfigured}
                    />
                )
            case 'sync':
                return (
                    <Sync
                        records={syncRecords}
                        loading={false}
                        syncing={syncing}
                        isConfigured={isConfigured}
                        onSync={handleSync}
                        onRefresh={handleRefresh}
                    />
                )
            case 'history':
                return (
                    <History
                        logs={logs}
                        loading={false}
                        totalCount={logs.length}
                        page={historyPage}
                        pageSize={10}
                        onPageChange={handleHistoryPageChange}
                        onClearHistory={handleClearHistory}
                    />
                )
            case 'settings':
                return (
                    <Settings
                        config={config || undefined}
                        loading={programsLoading}
                        saving={saving}
                        onSave={handleSaveConfig}
                        programs={programs}
                    />
                )
            default:
                return null
        }
    }

    return (
        <div className={classes.appContainer}>
            <Navigation currentPage={currentPage} onNavigate={handleNavigate} />
            <main className={classes.mainContent}>{renderPage()}</main>
        </div>
    )
}

export default MyApp
