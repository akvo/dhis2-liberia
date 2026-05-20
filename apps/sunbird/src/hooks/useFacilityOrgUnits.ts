import { useDataQuery } from '@dhis2/app-runtime'
import { useState, useEffect, useCallback, useMemo } from 'react'
import type { FacilityRecord, SyncStats } from '@/types'

const OSID_ATTR_CODE = 'SUNBIRD_OSID'
const DEFAULT_PAGE_SIZE = 10

interface UseFacilityOrgUnitsResult {
    records: FacilityRecord[]
    loading: boolean
    error: Error | null
    stats: SyncStats
    // Pagination
    page: number
    pageSize: number
    pageCount: number
    filteredTotal: number
    setPage: (page: number) => void
    setPageSize: (size: number) => void
    refetch: () => void
}

interface SyncHistoryResult {
    orgUnitId: string
    orgUnitName: string
    status: string
    error?: string
}

interface SyncHistoryEntry {
    results: SyncHistoryResult[]
}

// Query for OSID attribute ID
const osidAttrQuery = {
    osidAttr: {
        resource: 'attributes',
        params: {
            filter: `code:eq:${OSID_ATTR_CODE}`,
            fields: 'id',
        },
    },
}

export const useFacilityOrgUnits = (
    orgUnitGroupIds: string[],
    statusFilter: 'all' | 'pending' | 'synced' | 'error' = 'all'
): UseFacilityOrgUnitsResult => {
    const [allRecords, setAllRecords] = useState<FacilityRecord[]>([])
    const [stats, setStats] = useState<SyncStats>({ total: 0, synced: 0, pending: 0, error: 0 })
    const [loading, setLoading] = useState(false)
    const [error, setError] = useState<Error | null>(null)
    const [page, setPage] = useState(1)
    const [pageSize, setPageSize] = useState(DEFAULT_PAGE_SIZE)

    // Get OSID attribute ID
    const {
        data: osidData,
        loading: osidLoading,
        error: osidError,
        engine,
    } = useDataQuery<{
        osidAttr: { attributes: Array<{ id: string }> }
    }>(osidAttrQuery)

    const osidAttrId = osidData?.osidAttr?.attributes?.[0]?.id

    // Filter records by status
    const filteredRecords = useMemo(() => {
        if (statusFilter === 'all') {
            return allRecords
        }
        return allRecords.filter((r) => r.syncStatus === statusFilter)
    }, [allRecords, statusFilter])

    // Paginate filtered records
    const paginatedRecords = useMemo(() => {
        const startIndex = (page - 1) * pageSize
        return filteredRecords.slice(startIndex, startIndex + pageSize)
    }, [filteredRecords, page, pageSize])

    const pageCount = useMemo(() => {
        return Math.ceil(filteredRecords.length / pageSize)
    }, [filteredRecords.length, pageSize])

    // Reset page when filter changes
    useEffect(() => {
        setPage(1)
    }, [statusFilter])

    const fetchOrgUnits = useCallback(async () => {
        if (!engine || orgUnitGroupIds.length === 0) {
            setAllRecords([])
            setStats({ total: 0, synced: 0, pending: 0, error: 0 })
            return
        }

        setLoading(true)
        setError(null)

        try {
            // Build filter for org unit groups
            const groupFilter = orgUnitGroupIds.join(',')

            // Fetch org units and sync history in parallel
            const [orgUnitsResult, historyResult] = await Promise.all([
                engine.query({
                    orgUnits: {
                        resource: 'organisationUnits',
                        params: {
                            filter: `organisationUnitGroups.id:in:[${groupFilter}]`,
                            fields: 'id,name,code,shortName,geometry,ancestors[id,name,level],attributeValues[attribute[id,code],value]',
                            paging: false,
                        },
                    },
                }),
                engine.query({
                    history: {
                        resource: 'dataStore/sunbird-sync/history',
                    },
                }).catch(() => ({ history: [] })), // Return empty array if no history
            ])

            const orgUnits = (orgUnitsResult.orgUnits as any).organisationUnits || []
            const historyEntries = (historyResult.history as SyncHistoryEntry[]) || []

            // Build error map from most recent sync history
            // Only look at the most recent entry for each org unit
            const errorMap = new Map<string, string>()
            for (const entry of historyEntries) {
                for (const result of entry.results || []) {
                    if (result.status === 'error' && result.error && !errorMap.has(result.orgUnitId)) {
                        errorMap.set(result.orgUnitId, result.error)
                    }
                }
            }

            // Transform to FacilityRecord
            const transformed: FacilityRecord[] = orgUnits.map((ou: any) => {
                // Get OSID if exists
                let osid: string | undefined
                for (const av of ou.attributeValues || []) {
                    if (av.attribute?.code === OSID_ATTR_CODE || av.attribute?.id === osidAttrId) {
                        osid = av.value
                        break
                    }
                }

                // Build location string from ancestors
                const ancestors = ou.ancestors || []
                const locationParts: string[] = []

                // Sort ancestors by level and get names
                const sortedAncestors = [...ancestors].sort((a: any, b: any) => a.level - b.level)
                for (const ancestor of sortedAncestors) {
                    if (ancestor.level >= 2) { // Skip country level
                        locationParts.push(ancestor.name)
                    }
                }
                const location = locationParts.join(' > ')

                // Get coordinates if available
                let coordinates: { lon: number; lat: number } | undefined
                if (ou.geometry?.type === 'Point' && ou.geometry.coordinates?.length >= 2) {
                    coordinates = {
                        lon: ou.geometry.coordinates[0],
                        lat: ou.geometry.coordinates[1],
                    }
                }

                // Determine sync status
                // If synced (has OSID), it's synced regardless of past errors
                // If not synced but has error in history, it's error
                // Otherwise it's pending
                const errorMessage = errorMap.get(ou.id)
                let syncStatus: 'pending' | 'synced' | 'error' = 'pending'
                if (osid) {
                    syncStatus = 'synced'
                } else if (errorMessage) {
                    syncStatus = 'error'
                }

                return {
                    id: ou.id,
                    name: ou.name,
                    code: ou.code || '',
                    location,
                    coordinates,
                    syncStatus,
                    osid,
                    errorMessage: syncStatus === 'error' ? errorMessage : undefined,
                } as FacilityRecord
            })

            // Calculate stats
            const syncedCount = transformed.filter((r) => r.syncStatus === 'synced').length
            const errorCount = transformed.filter((r) => r.syncStatus === 'error').length
            const pendingCount = transformed.filter((r) => r.syncStatus === 'pending').length

            setStats({
                total: transformed.length,
                synced: syncedCount,
                pending: pendingCount,
                error: errorCount,
            })

            setAllRecords(transformed)
        } catch (err) {
            setError(err instanceof Error ? err : new Error('Failed to fetch org units'))
        } finally {
            setLoading(false)
        }
    }, [engine, orgUnitGroupIds, osidAttrId])

    // Fetch when dependencies change
    useEffect(() => {
        if (!osidLoading && orgUnitGroupIds.length > 0) {
            fetchOrgUnits()
        }
    }, [osidLoading, orgUnitGroupIds.join(',')])

    return {
        records: paginatedRecords,
        loading: osidLoading || loading,
        error: osidError || error || null,
        stats,
        page,
        pageSize,
        pageCount,
        filteredTotal: filteredRecords.length,
        setPage,
        setPageSize,
        refetch: fetchOrgUnits,
    }
}
