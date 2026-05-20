import i18n from '@dhis2/d2-i18n'
import {
    Card,
    IconCheckmarkCircle24,
    IconClock24,
    IconWorld24,
    CircularLoader,
    SingleSelect,
    SingleSelectOption,
    Field,
    Tag,
    NoticeBox,
} from '@dhis2/ui'
import React, { FC } from 'react'
import type { EntityMapping, SyncStats, OrgUnitGroup } from '@/types'
import classes from './Dashboard.module.css'

interface DashboardStats extends SyncStats {
    lastSyncTime?: string | null
}

interface DashboardProps {
    stats: DashboardStats
    loading?: boolean
    isConfigured?: boolean
    entityMappings: EntityMapping[]
    orgUnitGroups: OrgUnitGroup[]
    selectedMappingId?: string
    onMappingChange?: (mappingId: string) => void
}

const Dashboard: FC<DashboardProps> = ({
    stats,
    loading = false,
    isConfigured = false,
    entityMappings = [],
    orgUnitGroups = [],
    selectedMappingId,
    onMappingChange,
}) => {
    const getMappingLabel = (mapping: EntityMapping): string => {
        const groupNames = mapping.orgUnitGroupIds
            .map((gid) => {
                const group = orgUnitGroups.find((g) => g.id === gid)
                return group?.displayName || gid
            })
            .join(', ')
        return `${mapping.entityType} (${groupNames})`
    }

    const selectedMapping = entityMappings.find((m) => m.id === selectedMappingId)

    if (loading) {
        return (
            <div className={classes.loadingContainer}>
                <CircularLoader />
            </div>
        )
    }

    if (!isConfigured) {
        return (
            <div className={classes.container}>
                <Card className={classes.warningCard}>
                    <div className={classes.cardContent}>
                        <h3>{i18n.t('Configuration Required')}</h3>
                        <p>
                            {i18n.t(
                                'Please configure the Sunbird RC connection in Settings before syncing.'
                            )}
                        </p>
                    </div>
                </Card>
            </div>
        )
    }

    if (entityMappings.length === 0) {
        return (
            <div className={classes.container}>
                <NoticeBox warning title={i18n.t('No Entity Mappings')}>
                    {i18n.t(
                        'Please create at least one Entity Mapping in Settings to start syncing facilities.'
                    )}
                </NoticeBox>
            </div>
        )
    }

    const syncPercentage = stats.total > 0
        ? Math.round((stats.synced / stats.total) * 100)
        : 0

    return (
        <div className={classes.container}>
            <div className={classes.headerRow}>
                <h2>{i18n.t('Facility Sync Overview')}</h2>
                {selectedMapping && (
                    <Tag neutral>
                        {selectedMapping.entityType}
                    </Tag>
                )}
            </div>

            {entityMappings.length > 1 && onMappingChange && (
                <div className={classes.mappingSelector}>
                    <Field label={i18n.t('Entity Mapping')}>
                        <SingleSelect
                            selected={selectedMappingId}
                            onChange={({ selected }) => onMappingChange(selected || '')}
                            placeholder={i18n.t('Select a mapping')}
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
            )}

            <div className={classes.statsGrid}>
                <Card className={classes.statCard}>
                    <div className={classes.cardContent}>
                        <div className={classes.statHeader}>
                            <IconWorld24 />
                            <span>{i18n.t('Total Facilities')}</span>
                        </div>
                        <div className={classes.statValue}>
                            {stats.total}
                        </div>
                    </div>
                </Card>

                <Card className={classes.statCard}>
                    <div className={classes.cardContent}>
                        <div className={classes.statHeader}>
                            <IconCheckmarkCircle24 />
                            <span>{i18n.t('Synced')}</span>
                        </div>
                        <div className={classes.statValue}>
                            {stats.synced}
                        </div>
                        <div className={classes.statSubtext}>
                            {syncPercentage}% {i18n.t('complete')}
                        </div>
                    </div>
                </Card>

                <Card className={`${classes.statCard} ${stats.pending > 0 ? classes.pendingCard : ''}`}>
                    <div className={classes.cardContent}>
                        <div className={classes.statHeader}>
                            <IconClock24 />
                            <span>{i18n.t('Pending')}</span>
                        </div>
                        <div className={classes.statValue}>
                            {stats.pending}
                        </div>
                        {stats.pending > 0 && (
                            <div className={classes.statSubtext}>
                                {i18n.t('Ready to sync')}
                            </div>
                        )}
                    </div>
                </Card>

                <Card className={classes.statCard}>
                    <div className={classes.cardContent}>
                        <div className={classes.statHeader}>
                            <IconClock24 />
                            <span>{i18n.t('Last Sync')}</span>
                        </div>
                        <div className={classes.statTime}>
                            {stats.lastSyncTime ?? i18n.t('Never')}
                        </div>
                    </div>
                </Card>
            </div>

            {stats.total > 0 && (
                <div className={classes.progressSection}>
                    <div className={classes.progressLabel}>
                        {i18n.t('Sync Progress')}
                    </div>
                    <div className={classes.progressBar}>
                        <div
                            className={classes.progressFill}
                            style={{ width: `${syncPercentage}%` }}
                        />
                    </div>
                    <div className={classes.progressText}>
                        {i18n.t('{{synced}} of {{total}} facilities synced to Sunbird RC', {
                            synced: stats.synced,
                            total: stats.total,
                        })}
                    </div>
                </div>
            )}
        </div>
    )
}

export default Dashboard
