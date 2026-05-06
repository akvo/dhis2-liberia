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
} from '@dhis2/ui'
import React, { FC, useState } from 'react'
import classes from './Sync.module.css'

export interface TEIRecord {
    id: string
    displayName: string
    orgUnit: string
    lastUpdated: string
    syncStatus: 'pending' | 'synced' | 'error'
    errorMessage?: string
}

interface SyncProps {
    records?: TEIRecord[]
    loading?: boolean
    syncing?: boolean
    isConfigured?: boolean
    onSync: (selectedIds: string[]) => void
    onRefresh: () => void
}

const Sync: FC<SyncProps> = ({
    records = [],
    loading = false,
    syncing = false,
    isConfigured = false,
    onSync,
    onRefresh,
}) => {
    const [selectedIds, setSelectedIds] = useState<string[]>([])

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
    }

    const getStatusTag = (status: TEIRecord['syncStatus']) => {
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

    if (loading) {
        return (
            <div className={classes.loadingContainer}>
                <CircularLoader />
                <p>{i18n.t('Loading tracked entities...')}</p>
            </div>
        )
    }

    const pendingCount = records.filter((r) => r.syncStatus === 'pending').length

    return (
        <div className={classes.container}>
            <div className={classes.header}>
                <h2>{i18n.t('Sync to Sunbird RC')}</h2>
                <div className={classes.actions}>
                    <Button onClick={onRefresh} disabled={syncing}>
                        {i18n.t('Refresh')}
                    </Button>
                    <Button
                        primary
                        onClick={handleSync}
                        disabled={syncing || pendingCount === 0}
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

            {syncing && (
                <div className={classes.progressContainer}>
                    <LinearLoader />
                    <p>{i18n.t('Syncing records to Sunbird RC...')}</p>
                </div>
            )}

            {records.length === 0 ? (
                <Card>
                    <div className={classes.emptyState}>
                        <p>{i18n.t('No tracked entities found for the configured program.')}</p>
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
                                            selectedIds.length === records.length &&
                                            records.length > 0
                                        }
                                        indeterminate={
                                            selectedIds.length > 0 &&
                                            selectedIds.length < records.length
                                        }
                                        onChange={({ checked }) =>
                                            handleSelectAll(checked)
                                        }
                                    />
                                </DataTableColumnHeader>
                                <DataTableColumnHeader>
                                    {i18n.t('Name')}
                                </DataTableColumnHeader>
                                <DataTableColumnHeader>
                                    {i18n.t('Organisation Unit')}
                                </DataTableColumnHeader>
                                <DataTableColumnHeader>
                                    {i18n.t('Last Updated')}
                                </DataTableColumnHeader>
                                <DataTableColumnHeader>
                                    {i18n.t('Status')}
                                </DataTableColumnHeader>
                            </DataTableRow>
                        </DataTableHead>
                        <DataTableBody>
                            {records.map((record) => (
                                <DataTableRow key={record.id}>
                                    <DataTableCell>
                                        <Checkbox
                                            checked={selectedIds.includes(
                                                record.id
                                            )}
                                            onChange={({ checked }) =>
                                                handleSelect(record.id, checked)
                                            }
                                        />
                                    </DataTableCell>
                                    <DataTableCell>
                                        {record.displayName}
                                    </DataTableCell>
                                    <DataTableCell>
                                        {record.orgUnit}
                                    </DataTableCell>
                                    <DataTableCell>
                                        {record.lastUpdated}
                                    </DataTableCell>
                                    <DataTableCell>
                                        {getStatusTag(record.syncStatus)}
                                        {record.errorMessage && (
                                            <span className={classes.errorText}>
                                                {record.errorMessage}
                                            </span>
                                        )}
                                    </DataTableCell>
                                </DataTableRow>
                            ))}
                        </DataTableBody>
                    </DataTable>
                </Card>
            )}
        </div>
    )
}

export default Sync
