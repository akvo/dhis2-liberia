import { useDataQuery } from '@dhis2/app-runtime'

interface Program {
    id: string
    displayName: string
}

interface ProgramsQueryResult {
    programs: {
        programs: Program[]
    }
}

const programsQuery = {
    programs: {
        resource: 'programs',
        params: {
            fields: 'id,displayName',
            paging: false,
            filter: 'programType:eq:WITH_REGISTRATION',
        },
    },
}

interface UseProgramsResult {
    programs: Program[]
    loading: boolean
    error: Error | null
}

export const usePrograms = (): UseProgramsResult => {
    const { data, loading, error } =
        useDataQuery<ProgramsQueryResult>(programsQuery)

    return {
        programs: data?.programs?.programs || [],
        loading,
        error: error || null,
    }
}
