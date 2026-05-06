import { useDataQuery } from '@dhis2/app-runtime'
import { useMemo, useEffect, useState } from 'react'
import type { TEIRecord } from '@/pages/Sync'

interface TrackedEntityInstance {
    trackedEntityInstance: string
    orgUnit: string
    attributes: Array<{
        attribute: string
        value: string
    }>
    lastUpdated: string
}

// Attribute codes from config.json
const SYNC_STATUS_CODE = 'SYNC_STATUS_ATTR'
const GEO_CODE = 'GEO_CODE'
const PENDING_STATUS = 'SYNC_STATUS_PENDING'
const SYNCED_STATUS = 'SYNC_STATUS_SYNCED'
const FAILED_STATUS = 'SYNC_STATUS_FAILED'

const metadataQuery = {
    rootOu: {
        resource: 'organisationUnits',
        params: {
            filter: 'level:eq:1',
            fields: 'id',
            paging: false,
        },
    },
    attributes: {
        resource: 'trackedEntityAttributes',
        params: {
            fields: 'id,code,displayName',
            paging: false,
        },
    },
    orgUnits: {
        resource: 'organisationUnits',
        params: {
            fields: 'id,displayName',
            paging: false,
        },
    },
}

interface UsePendingTeisResult {
    records: TEIRecord[]
    loading: boolean
    error: Error | null
    refetch: () => void
    stats: {
        pending: number
        synced: number
        failed: number
        total: number
    }
}

export const usePendingTeis = (programId: string | undefined): UsePendingTeisResult => {
    const [records, setRecords] = useState<TEIRecord[]>([])
    const [stats, setStats] = useState({ pending: 0, synced: 0, failed: 0, total: 0 })
    const [teiLoading, setTeiLoading] = useState(false)
    const [teiError, setTeiError] = useState<Error | null>(null)

    // Fetch metadata
    const {
        data: metaData,
        loading: metaLoading,
        error: metaError,
        engine,
    } = useDataQuery<{
        rootOu: { organisationUnits: Array<{ id: string }> }
        attributes: { trackedEntityAttributes: Array<{ id: string; code: string; displayName: string }> }
        orgUnits: { organisationUnits: Array<{ id: string; displayName: string }> }
    }>(metadataQuery)

    const rootOuId = metaData?.rootOu?.organisationUnits?.[0]?.id
    const attributes = metaData?.attributes?.trackedEntityAttributes || []
    const orgUnits = metaData?.orgUnits?.organisationUnits || []

    // Fetch TEIs when we have metadata and programId
    const fetchTeis = async () => {
        if (!programId || !rootOuId || !engine) return

        setTeiLoading(true)
        setTeiError(null)

        try {
            const result = await engine.query({
                teis: {
                    resource: 'trackedEntityInstances',
                    params: {
                        ou: rootOuId,
                        ouMode: 'DESCENDANTS',
                        program: programId,
                        fields: 'trackedEntityInstance,orgUnit,attributes[attribute,value],lastUpdated',
                        paging: false,
                    },
                },
            })

            const teis = (result.teis as { trackedEntityInstances: TrackedEntityInstance[] }).trackedEntityInstances || []

            // Build lookup maps
            const attrCodeMap = new Map<string, string>()
            attributes.forEach((attr) => {
                attrCodeMap.set(attr.id, attr.code)
            })

            const ouNameMap = new Map<string, string>()
            orgUnits.forEach((ou) => {
                ouNameMap.set(ou.id, ou.displayName)
            })

            // Find attribute IDs
            let syncStatusId = ''
            let geoCodeId = ''
            attributes.forEach((attr) => {
                if (attr.code === SYNC_STATUS_CODE) syncStatusId = attr.id
                if (attr.code === GEO_CODE) geoCodeId = attr.id
            })

            // Transform TEIs to records
            const transformedRecords: TEIRecord[] = teis.map((tei) => {
                const getAttrValue = (attrId: string): string => {
                    const attr = tei.attributes?.find((a) => a.attribute === attrId)
                    return attr?.value || ''
                }

                const syncStatusValue = getAttrValue(syncStatusId)
                let syncStatus: TEIRecord['syncStatus'] = 'pending'
                if (syncStatusValue === SYNCED_STATUS) {
                    syncStatus = 'synced'
                } else if (syncStatusValue === FAILED_STATUS) {
                    syncStatus = 'error'
                }

                const geoCode = getAttrValue(geoCodeId)

                return {
                    id: tei.trackedEntityInstance,
                    displayName: geoCode || tei.trackedEntityInstance,
                    orgUnit: ouNameMap.get(tei.orgUnit) || tei.orgUnit,
                    lastUpdated: new Date(tei.lastUpdated).toLocaleString(),
                    syncStatus,
                }
            })

            // Calculate stats
            const newStats = {
                pending: transformedRecords.filter((r) => r.syncStatus === 'pending').length,
                synced: transformedRecords.filter((r) => r.syncStatus === 'synced').length,
                failed: transformedRecords.filter((r) => r.syncStatus === 'error').length,
                total: transformedRecords.length,
            }

            setRecords(transformedRecords)
            setStats(newStats)
        } catch (err) {
            setTeiError(err instanceof Error ? err : new Error('Failed to fetch TEIs'))
        } finally {
            setTeiLoading(false)
        }
    }

    // Fetch TEIs when metadata and programId are ready
    useEffect(() => {
        if (programId && rootOuId && !metaLoading) {
            fetchTeis()
        }
    }, [programId, rootOuId, metaLoading])

    const refetch = () => {
        fetchTeis()
    }

    return {
        records,
        loading: metaLoading || teiLoading,
        error: metaError || teiError || null,
        refetch,
        stats,
    }
}
