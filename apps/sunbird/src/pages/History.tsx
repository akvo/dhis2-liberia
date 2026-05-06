import i18n from '@dhis2/d2-i18n'
import {
    Card,
    CircularLoader,
    DataTable,
    DataTableHead,
    DataTableBody,
    DataTableRow,
    DataTableCell,
    DataTableColumnHeader,
    Tag,
    Button,
    Pagination,
} from '@dhis2/ui'
import React, { FC, useState } from 'react'
import classes from './History.module.css'

export interface SyncLogEntry {
    id: string
    timestamp: string
    recordCount: number
    successCount: number
    errorCount: number
    status: 'success' | 'partial' | 'failed'
    details?: string
}

interface HistoryProps {
    logs?: SyncLogEntry[]
    loading?: boolean
    totalCount?: number
    page?: number
    pageSize?: number
    onPageChange: (page: number) => void
    onClearHistory: () => void
}

const History: FC<HistoryProps> = ({
    logs = [],
    loading = false,
    totalCount = 0,
    page = 1,
    pageSize = 10,
    onPageChange,
    onClearHistory,
}) => {
    const [expandedId, setExpandedId] = useState<string | null>(null)

    const getStatusTag = (status: SyncLogEntry['status']) => {
        switch (status) {
            case 'success':
                return <Tag positive>{i18n.t('Success')}</Tag>
            case 'partial':
                return <Tag neutral>{i18n.t('Partial')}</Tag>
            case 'failed':
                return <Tag negative>{i18n.t('Failed')}</Tag>
            default:
                return <Tag>{status}</Tag>
        }
    }

    const toggleExpand = (id: string) => {
        setExpandedId(expandedId === id ? null : id)
    }

    if (loading) {
        return (
            <div className={classes.loadingContainer}>
                <CircularLoader />
            </div>
        )
    }

    return (
        <div className={classes.container}>
            <div className={classes.header}>
                <h2>{i18n.t('Sync History')}</h2>
                {logs.length > 0 && (
                    <Button
                        small
                        secondary
                        destructive
                        onClick={onClearHistory}
                    >
                        {i18n.t('Clear History')}
                    </Button>
                )}
            </div>

            {logs.length === 0 ? (
                <Card>
                    <div className={classes.emptyState}>
                        <p>{i18n.t('No sync history available.')}</p>
                    </div>
                </Card>
            ) : (
                <>
                    <Card>
                        <DataTable>
                            <DataTableHead>
                                <DataTableRow>
                                    <DataTableColumnHeader>
                                        {i18n.t('Timestamp')}
                                    </DataTableColumnHeader>
                                    <DataTableColumnHeader>
                                        {i18n.t('Records')}
                                    </DataTableColumnHeader>
                                    <DataTableColumnHeader>
                                        {i18n.t('Success')}
                                    </DataTableColumnHeader>
                                    <DataTableColumnHeader>
                                        {i18n.t('Errors')}
                                    </DataTableColumnHeader>
                                    <DataTableColumnHeader>
                                        {i18n.t('Status')}
                                    </DataTableColumnHeader>
                                    <DataTableColumnHeader width="100px">
                                        {i18n.t('Details')}
                                    </DataTableColumnHeader>
                                </DataTableRow>
                            </DataTableHead>
                            <DataTableBody>
                                {logs.map((log) => (
                                    <React.Fragment key={log.id}>
                                        <DataTableRow>
                                            <DataTableCell>
                                                {log.timestamp}
                                            </DataTableCell>
                                            <DataTableCell>
                                                {log.recordCount}
                                            </DataTableCell>
                                            <DataTableCell>
                                                {log.successCount}
                                            </DataTableCell>
                                            <DataTableCell>
                                                {log.errorCount}
                                            </DataTableCell>
                                            <DataTableCell>
                                                {getStatusTag(log.status)}
                                            </DataTableCell>
                                            <DataTableCell>
                                                {log.details && (
                                                    <Button
                                                        small
                                                        secondary
                                                        onClick={() =>
                                                            toggleExpand(log.id)
                                                        }
                                                    >
                                                        {expandedId === log.id
                                                            ? i18n.t('Hide')
                                                            : i18n.t('View')}
                                                    </Button>
                                                )}
                                            </DataTableCell>
                                        </DataTableRow>
                                        {expandedId === log.id && log.details && (
                                            <DataTableRow>
                                                <DataTableCell colSpan="6">
                                                    <pre
                                                        className={
                                                            classes.detailsBox
                                                        }
                                                    >
                                                        {log.details}
                                                    </pre>
                                                </DataTableCell>
                                            </DataTableRow>
                                        )}
                                    </React.Fragment>
                                ))}
                            </DataTableBody>
                        </DataTable>
                    </Card>

                    {totalCount > pageSize && (
                        <div className={classes.pagination}>
                            <Pagination
                                page={page}
                                pageCount={Math.ceil(totalCount / pageSize)}
                                pageSize={pageSize}
                                total={totalCount}
                                onPageChange={onPageChange}
                                hidePageSizeSelect
                            />
                        </div>
                    )}
                </>
            )}
        </div>
    )
}

export default History
