import { useDataQuery } from '@dhis2/app-runtime'
import type { OrgUnitGroup } from '@/types'

const query = {
    groups: {
        resource: 'organisationUnitGroups',
        params: {
            fields: 'id,displayName,code',
            paging: false,
        },
    },
}

interface QueryResult {
    groups: {
        organisationUnitGroups: Array<{
            id: string
            displayName: string
            code: string
        }>
    }
}

interface UseOrgUnitGroupsResult {
    groups: OrgUnitGroup[]
    loading: boolean
    error: Error | null
}

export const useOrgUnitGroups = (): UseOrgUnitGroupsResult => {
    const { data, loading, error } = useDataQuery<QueryResult>(query)

    const groups: OrgUnitGroup[] = (data?.groups?.organisationUnitGroups || []).map(
        (g) => ({
            id: g.id,
            displayName: g.displayName,
            code: g.code,
        })
    )

    return {
        groups,
        loading,
        error: error || null,
    }
}
