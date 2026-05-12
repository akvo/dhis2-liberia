import i18n from '@dhis2/d2-i18n'
import {
    Card,
    IconSync24,
    IconCheckmarkCircle24,
    IconError24,
    IconClock24,
    CircularLoader,
    SingleSelect,
    SingleSelectOption,
    Field,
    Tag,
} from '@dhis2/ui'
import React, { FC } from 'react'
import type { ProgramConfig } from './Settings'
import classes from './Dashboard.module.css'

interface SyncStats {
    totalSynced: number
    lastSyncTime: string | null
    pendingCount: number
    errorCount: number
}

interface DashboardProps {
    stats?: SyncStats
    loading?: boolean
    isConfigured?: boolean
    programs?: ProgramConfig[]
    dhis2Programs?: Array<{ id: string; displayName: string }>
    selectedProgramId?: string
    onProgramChange?: (programId: string) => void
}

const Dashboard: FC<DashboardProps> = ({
    stats,
    loading = false,
    isConfigured = false,
    programs = [],
    dhis2Programs = [],
    selectedProgramId,
    onProgramChange,
}) => {
    const getProgramDisplayName = (programId: string): string => {
        const dhis2Program = dhis2Programs.find(p => p.id === programId)
        return dhis2Program?.displayName || programId
    }

    const selectedProgram = programs.find(p => p.programId === selectedProgramId)
    const enabledPrograms = programs.filter(p => p.enabled)

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

    return (
        <div className={classes.container}>
            <div className={classes.headerRow}>
                <h2>{i18n.t('Sync Overview')}</h2>
                {selectedProgram && (
                    <Tag neutral>
                        {getProgramDisplayName(selectedProgram.programId)} → {selectedProgram.entityType}
                    </Tag>
                )}
            </div>

            {enabledPrograms.length > 1 && onProgramChange && (
                <div className={classes.programSelector}>
                    <Field label={i18n.t('Select Program')}>
                        <SingleSelect
                            selected={selectedProgramId}
                            onChange={({ selected }) => onProgramChange(selected || '')}
                            placeholder={i18n.t('Choose a program')}
                        >
                            {enabledPrograms.map((prog) => (
                                <SingleSelectOption
                                    key={prog.programId}
                                    label={`${getProgramDisplayName(prog.programId)} → ${prog.entityType}`}
                                    value={prog.programId}
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
                            <IconCheckmarkCircle24 />
                            <span>{i18n.t('Total Synced')}</span>
                        </div>
                        <div className={classes.statValue}>
                            {stats?.totalSynced ?? 0}
                        </div>
                    </div>
                </Card>

                <Card className={classes.statCard}>
                    <div className={classes.cardContent}>
                        <div className={classes.statHeader}>
                            <IconSync24 />
                            <span>{i18n.t('Pending')}</span>
                        </div>
                        <div className={classes.statValue}>
                            {stats?.pendingCount ?? 0}
                        </div>
                    </div>
                </Card>

                <Card className={classes.statCard}>
                    <div className={classes.cardContent}>
                        <div className={classes.statHeader}>
                            <IconError24 />
                            <span>{i18n.t('Errors')}</span>
                        </div>
                        <div className={classes.statValue}>
                            {stats?.errorCount ?? 0}
                        </div>
                    </div>
                </Card>

                <Card className={classes.statCard}>
                    <div className={classes.cardContent}>
                        <div className={classes.statHeader}>
                            <IconClock24 />
                            <span>{i18n.t('Last Sync')}</span>
                        </div>
                        <div className={classes.statTime}>
                            {stats?.lastSyncTime ?? i18n.t('Never')}
                        </div>
                    </div>
                </Card>
            </div>
        </div>
    )
}

export default Dashboard
