import i18n from '@dhis2/d2-i18n'
import { CircularLoader, NoticeBox } from '@dhis2/ui'
import React, { FC, useState, useCallback, useEffect, useMemo } from 'react'
import classes from '@/App.module.css'
import { Navigation, PageKey } from '@/components'
import {
    useConfig,
    useSyncHistory,
    useOrgUnitGroups,
    useEntityMappings,
    useFacilityOrgUnits,
    useSyncQueue,
} from '@/hooks'
import { Dashboard, Settings, Sync, History, Mappings } from '@/pages'
import type { SunbirdConfig, EntityMapping } from '@/types'

const MyApp: FC = () => {
    const [currentPage, setCurrentPage] = useState<PageKey>('dashboard')
    const [historyPage, setHistoryPage] = useState(1)
    const [syncQueued, setSyncQueued] = useState(false)
    const [selectedMappingId, setSelectedMappingId] = useState<string>('')
    const [statusFilter, setStatusFilter] = useState<'all' | 'pending' | 'synced' | 'error'>('all')

    // Hooks for data
    const { config, loading: configLoading, saving, saveConfig, isConfigured, error: configError } = useConfig()
    const { logs, loading: historyLoading, refetchHistory, clearHistory } = useSyncHistory()
    const { groups: orgUnitGroups, loading: groupsLoading } = useOrgUnitGroups()
    const {
        mappings: entityMappings,
        loading: mappingsLoading,
        saving: mappingsSaving,
        addMapping,
        updateMapping,
        deleteMapping,
    } = useEntityMappings()
    const { queueSyncRequest } = useSyncQueue()

    const [syncing, setSyncing] = useState(false)

    // Get org unit group IDs for selected mapping
    const selectedMapping = useMemo(() => {
        return entityMappings.find((m) => m.id === selectedMappingId)
    }, [entityMappings, selectedMappingId])

    const selectedGroupIds = useMemo(() => {
        return selectedMapping?.orgUnitGroupIds || []
    }, [selectedMapping])

    // Fetch facilities for selected mapping
    const {
        records: facilityRecords,
        loading: facilitiesLoading,
        stats: facilityStats,
        page: facilityPage,
        pageSize: facilityPageSize,
        pageCount: facilityPageCount,
        filteredTotal: facilityFilteredTotal,
        setPage: setFacilityPage,
        setPageSize: setFacilityPageSize,
        refetch: refetchFacilities,
    } = useFacilityOrgUnits(selectedGroupIds, statusFilter)

    // Auto-select first mapping when mappings load
    useEffect(() => {
        if (entityMappings.length > 0 && !selectedMappingId) {
            setSelectedMappingId(entityMappings[0].id)
        }
    }, [entityMappings, selectedMappingId])

    // Auto-refresh after sync is queued
    useEffect(() => {
        if (syncQueued) {
            const timer = setTimeout(() => {
                refetchHistory()
                refetchFacilities()
                setSyncQueued(false)
            }, 3000)
            return () => clearTimeout(timer)
        }
    }, [syncQueued, refetchHistory, refetchFacilities])

    const handleNavigate = useCallback((page: PageKey) => {
        setCurrentPage(page)
    }, [])

    const handleSaveConfig = useCallback(
        async (newConfig: SunbirdConfig) => {
            await saveConfig(newConfig)
        },
        [saveConfig]
    )

    const handleSaveMapping = useCallback(
        async (mapping: EntityMapping) => {
            const existing = entityMappings.find((m) => m.id === mapping.id)
            if (existing) {
                await updateMapping(mapping)
            } else {
                await addMapping(mapping)
            }
        },
        [entityMappings, addMapping, updateMapping]
    )

    const handleDeleteMapping = useCallback(
        async (id: string) => {
            await deleteMapping(id)
            if (selectedMappingId === id) {
                setSelectedMappingId('')
            }
        },
        [deleteMapping, selectedMappingId]
    )

    const handleMappingChange = useCallback((mappingId: string) => {
        setSelectedMappingId(mappingId)
        setStatusFilter('all')
    }, [])

    const handleStatusFilterChange = useCallback((status: 'all' | 'pending' | 'synced' | 'error') => {
        setStatusFilter(status)
    }, [])

    const handleSync = useCallback(
        async (selectedIds: string[]) => {
            if (!selectedMappingId || !selectedMapping) {
                console.error('No mapping selected')
                return
            }
            setSyncing(true)
            try {
                // Queue sync request for the worker to process
                const requestId = await queueSyncRequest(
                    selectedMappingId,
                    selectedIds.length > 0 ? selectedIds : undefined
                )
                console.log(`Sync request queued: ${requestId}`)
                setSyncQueued(true)
            } catch (err) {
                console.error('Failed to queue sync:', err)
            } finally {
                setSyncing(false)
            }
        },
        [queueSyncRequest, selectedMappingId, selectedMapping]
    )

    const handleRefresh = useCallback(() => {
        refetchFacilities()
    }, [refetchFacilities])

    const handleClearHistory = useCallback(async () => {
        await clearHistory()
    }, [clearHistory])

    const handleHistoryPageChange = useCallback((page: number) => {
        setHistoryPage(page)
    }, [])

    // Calculate dashboard stats
    const dashboardStats = {
        total: facilityStats.total,
        synced: facilityStats.synced,
        pending: facilityStats.pending,
        lastSyncTime: logs.length > 0 ? new Date(logs[0].timestamp).toLocaleString() : null,
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

    const isLoading = configLoading || historyLoading || groupsLoading || mappingsLoading

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
                        stats={dashboardStats}
                        loading={facilitiesLoading}
                        isConfigured={isConfigured}
                        entityMappings={entityMappings}
                        orgUnitGroups={orgUnitGroups}
                        selectedMappingId={selectedMappingId}
                        onMappingChange={handleMappingChange}
                    />
                )
            case 'sync':
                return (
                    <Sync
                        records={facilityRecords}
                        stats={facilityStats}
                        loading={facilitiesLoading}
                        syncing={syncing}
                        isConfigured={isConfigured}
                        entityMappings={entityMappings}
                        orgUnitGroups={orgUnitGroups}
                        selectedMappingId={selectedMappingId}
                        statusFilter={statusFilter}
                        page={facilityPage}
                        pageSize={facilityPageSize}
                        pageCount={facilityPageCount}
                        filteredTotal={facilityFilteredTotal}
                        onPageChange={setFacilityPage}
                        onPageSizeChange={setFacilityPageSize}
                        onMappingChange={handleMappingChange}
                        onStatusFilterChange={handleStatusFilterChange}
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
                        onRefresh={refetchHistory}
                    />
                )
            case 'mappings':
                return (
                    <Mappings
                        entityMappings={entityMappings}
                        orgUnitGroups={orgUnitGroups}
                        sunbirdUrl={config?.sunbirdUrl}
                        loading={groupsLoading}
                        saving={mappingsSaving}
                        onSaveMapping={handleSaveMapping}
                        onDeleteMapping={handleDeleteMapping}
                    />
                )
            case 'settings':
                return (
                    <Settings
                        config={config || undefined}
                        loading={configLoading}
                        saving={saving}
                        onSaveConfig={handleSaveConfig}
                    />
                )
            default:
                return null
        }
    }

    return (
        <div className={classes.appContainer}>
            <Navigation currentPage={currentPage} onNavigate={handleNavigate} isConfigured={isConfigured} />
            <main className={classes.mainContent}>{renderPage()}</main>
        </div>
    )
}

export default MyApp
