import i18n from '@dhis2/d2-i18n'
import {
    Card,
    Button,
    NoticeBox,
    CircularLoader,
    LinearLoader,
    DataTable,
    DataTableHead,
    DataTableBody,
    DataTableRow,
    DataTableCell,
    DataTableColumnHeader,
    Tag,
    Checkbox,
    SingleSelect,
    SingleSelectOption,
    Field,
    SegmentedControl,
    Pagination,
} from '@dhis2/ui'
import React, { FC, useState, useMemo } from 'react'
import type { EntityMapping, FacilityRecord, SyncStats, OrgUnitGroup } from '@/types'
import classes from './Sync.module.css'

interface SyncProps {
    records: FacilityRecord[]
    stats: SyncStats
    loading?: boolean
    syncing?: boolean
    isConfigured?: boolean
    entityMappings: EntityMapping[]
    orgUnitGroups: OrgUnitGroup[]
    selectedMappingId?: string
    statusFilter: 'all' | 'pending' | 'synced' | 'error'
    // Pagination
    page: number
    pageSize: number
    pageCount: number
    filteredTotal: number
    onPageChange: (page: number) => void
    onPageSizeChange: (pageSize: number) => void
    onMappingChange: (mappingId: string) => void
    onStatusFilterChange: (status: 'all' | 'pending' | 'synced' | 'error') => void
    onSync: (selectedIds: string[]) => void
    onRefresh: () => void
}

const Sync: FC<SyncProps> = ({
    records = [],
    stats,
    loading = false,
    syncing = false,
    isConfigured = false,
    entityMappings = [],
    orgUnitGroups = [],
    selectedMappingId,
    statusFilter,
    page,
    pageSize,
    pageCount,
    filteredTotal,
    onPageChange,
    onPageSizeChange,
    onMappingChange,
    onStatusFilterChange,
    onSync,
    onRefresh,
}) => {
    const [selectedIds, setSelectedIds] = useState<string[]>([])

    const selectedMapping = useMemo(() => {
        return entityMappings.find((m) => m.id === selectedMappingId)
    }, [entityMappings, selectedMappingId])

    const getMappingLabel = (mapping: EntityMapping): string => {
        const groupNames = mapping.orgUnitGroupIds
            .map((gid) => {
                const group = orgUnitGroups.find((g) => g.id === gid)
                return group?.displayName || gid
            })
            .join(', ')
        return `${mapping.entityType} (${groupNames})`
    }

    const handleSelectAll = (checked: boolean) => {
        if (checked) {
            setSelectedIds(records.map((r) => r.id))
        } else {
            setSelectedIds([])
        }
    }

    const handleSelect = (id: string, checked: boolean) => {
        if (checked) {
            setSelectedIds((prev) => [...prev, id])
        } else {
            setSelectedIds((prev) => prev.filter((i) => i !== id))
        }
    }

    const handleSync = () => {
        const idsToSync =
            selectedIds.length > 0
                ? selectedIds
                : records.filter((r) => r.syncStatus === 'pending').map((r) => r.id)
        onSync(idsToSync)
        setSelectedIds([])
    }

    const getStatusTag = (status: FacilityRecord['syncStatus']) => {
        switch (status) {
            case 'synced':
                return <Tag positive>{i18n.t('Synced')}</Tag>
            case 'error':
                return <Tag negative>{i18n.t('Error')}</Tag>
            default:
                return <Tag neutral>{i18n.t('Pending')}</Tag>
        }
    }

    if (!isConfigured) {
        return (
            <div className={classes.container}>
                <NoticeBox warning title={i18n.t('Configuration Required')}>
                    {i18n.t(
                        'Please configure the Sunbird RC connection in Settings before syncing.'
                    )}
                </NoticeBox>
            </div>
        )
    }

    if (entityMappings.length === 0) {
        return (
            <div className={classes.container}>
                <NoticeBox warning title={i18n.t('No Entity Mappings')}>
                    {i18n.t(
                        'Please create at least one Entity Mapping in Settings to define which Org Unit Groups sync to Sunbird.'
                    )}
                </NoticeBox>
            </div>
        )
    }

    const pendingCount = stats.pending

    return (
        <div className={classes.container}>
            <div className={classes.header}>
                <h2>{i18n.t('Sync Facilities to Sunbird RC')}</h2>
                <div className={classes.actions}>
                    <Button onClick={onRefresh} disabled={syncing || loading}>
                        {i18n.t('Refresh')}
                    </Button>
                    <Button
                        primary
                        onClick={handleSync}
                        disabled={syncing || pendingCount === 0 || !selectedMappingId}
                    >
                        {syncing
                            ? i18n.t('Syncing...')
                            : selectedIds.length > 0
                              ? i18n.t('Sync Selected ({{count}})', {
                                    count: selectedIds.length,
                                })
                              : i18n.t('Sync All Pending ({{count}})', {
                                    count: pendingCount,
                                })}
                    </Button>
                </div>
            </div>

            <div className={classes.filterRow}>
                <div className={classes.mappingSelector}>
                    <Field label={i18n.t('Entity Mapping')}>
                        <SingleSelect
                            selected={selectedMappingId}
                            onChange={({ selected }) => {
                                onMappingChange(selected || '')
                                setSelectedIds([])
                            }}
                            placeholder={i18n.t('Select an entity mapping')}
                        >
                            {entityMappings.map((mapping) => (
                                <SingleSelectOption
                                    key={mapping.id}
                                    label={getMappingLabel(mapping)}
                                    value={mapping.id}
                                />
                            ))}
                        </SingleSelect>
                    </Field>
                </div>

                {selectedMappingId && (
                    <div className={classes.statusFilter}>
                        <Field label={i18n.t('Status Filter')}>
                            <SegmentedControl
                                selected={statusFilter}
                                onChange={({ value }) =>
                                    onStatusFilterChange(value as 'all' | 'pending' | 'synced' | 'error')
                                }
                                options={[
                                    {
                                        value: 'all',
                                        label: i18n.t('All ({{count}})', { count: stats.total }),
                                    },
                                    {
                                        value: 'pending',
                                        label: i18n.t('Pending ({{count}})', { count: stats.pending }),
                                    },
                                    {
                                        value: 'synced',
                                        label: i18n.t('Synced ({{count}})', { count: stats.synced }),
                                    },
                                    {
                                        value: 'error',
                                        label: i18n.t('Error ({{count}})', { count: stats.error }),
                                    },
                                ]}
                            />
                        </Field>
                    </div>
                )}
            </div>

            {syncing && (
                <div className={classes.progressContainer}>
                    <LinearLoader />
                    <p>{i18n.t('Queuing sync request...')}</p>
                </div>
            )}

            {loading ? (
                <div className={classes.loadingContainer}>
                    <CircularLoader />
                    <p>{i18n.t('Loading facilities...')}</p>
                </div>
            ) : !selectedMappingId ? (
                <Card>
                    <div className={classes.emptyState}>
                        <p>{i18n.t('Select an entity mapping above to view facilities.')}</p>
                    </div>
                </Card>
            ) : records.length === 0 ? (
                <Card>
                    <div className={classes.emptyState}>
                        <p>
                            {statusFilter === 'all'
                                ? i18n.t('No facilities found for the selected mapping.')
                                : statusFilter === 'pending'
                                  ? i18n.t('No pending facilities. All facilities have been synced!')
                                  : i18n.t('No synced facilities yet.')}
                        </p>
                    </div>
                </Card>
            ) : (
                <Card>
                    <DataTable>
                        <DataTableHead>
                            <DataTableRow>
                                <DataTableColumnHeader width="48px">
                                    <Checkbox
                                        checked={
                                            selectedIds.length === records.length && records.length > 0
                                        }
                                        indeterminate={
                                            selectedIds.length > 0 && selectedIds.length < records.length
                                        }
                                        onChange={({ checked }) => handleSelectAll(checked)}
                                    />
                                </DataTableColumnHeader>
                                <DataTableColumnHeader>{i18n.t('Facility Name')}</DataTableColumnHeader>
                                <DataTableColumnHeader>{i18n.t('Code')}</DataTableColumnHeader>
                                <DataTableColumnHeader>{i18n.t('Location')}</DataTableColumnHeader>
                                <DataTableColumnHeader>{i18n.t('Status')}</DataTableColumnHeader>
                            </DataTableRow>
                        </DataTableHead>
                        <DataTableBody>
                            {records.map((record) => (
                                <DataTableRow key={record.id}>
                                    <DataTableCell>
                                        <Checkbox
                                            checked={selectedIds.includes(record.id)}
                                            onChange={({ checked }) => handleSelect(record.id, checked)}
                                            disabled={record.syncStatus === 'synced'}
                                        />
                                    </DataTableCell>
                                    <DataTableCell>{record.name}</DataTableCell>
                                    <DataTableCell>
                                        <code>{record.code || '-'}</code>
                                    </DataTableCell>
                                    <DataTableCell>{record.location || '-'}</DataTableCell>
                                    <DataTableCell>
                                        <div className={classes.statusCell}>
                                            {getStatusTag(record.syncStatus)}
                                            {record.osid && (
                                                <span className={classes.osidText}>
                                                    OSID: {record.osid.substring(0, 8)}...
                                                </span>
                                            )}
                                            {record.errorMessage && (
                                                <span className={classes.errorText}>
                                                    {record.errorMessage}
                                                </span>
                                            )}
                                        </div>
                                    </DataTableCell>
                                </DataTableRow>
                            ))}
                        </DataTableBody>
                    </DataTable>
                    {pageCount > 1 && (
                        <div className={classes.paginationContainer}>
                            <Pagination
                                page={page}
                                pageSize={pageSize}
                                pageCount={pageCount}
                                total={filteredTotal}
                                onPageChange={onPageChange}
                                onPageSizeChange={onPageSizeChange}
                                pageSizes={['10', '25', '50', '100']}
                            />
                        </div>
                    )}
                </Card>
            )}

            {selectedMapping && (
                <div className={classes.mappingInfo}>
                    <NoticeBox title={i18n.t('Sync Details')}>
                        <p>
                            {i18n.t('Entity Type')}: <strong>{selectedMapping.entityType}</strong>
                        </p>
                        <p>
                            {i18n.t('Field Mappings')}: {selectedMapping.fieldMappings.length}
                        </p>
                    </NoticeBox>
                </div>
            )}
        </div>
    )
}

export default Sync
