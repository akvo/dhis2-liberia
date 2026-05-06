import i18n from '@dhis2/d2-i18n'
import {
    Card,
    IconSync24,
    IconCheckmarkCircle24,
    IconError24,
    IconClock24,
    CircularLoader,
} from '@dhis2/ui'
import React, { FC } from 'react'
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
}

const Dashboard: FC<DashboardProps> = ({
    stats,
    loading = false,
    isConfigured = false,
}) => {
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
            <h2>{i18n.t('Sync Overview')}</h2>

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
